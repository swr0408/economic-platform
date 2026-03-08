"""
NZ 経常収支（Current Account Balance）サービス

指標:
- Current Account Balance (経常収支): 十億NZD
- QoQ Change (前期増減幅): 十億NZD

データソース:
- Stats NZ Balance of Payments and International Investment Position CSV
- シリーズID: BOPQ.S06AC100000000D = Current Account Balance
- MAGNTUDE=6 → 百万NZD → /1000 で十億NZD
- 期間フォーマット: YYYY.MM (MM = 四半期末月: 03=Q1, 06=Q2, 09=Q3, 12=Q4)
- 単一CSVファイルに1971年からの全履歴が含まれる

発表スケジュール:
- 四半期（前四半期分を約3ヶ月後に発表）
- FMPイベント: "Current Account"

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import json
import io
import html
import re
import csv
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_current_account_balance_cache.json"

# FMPパターン
FMP_EVENT_PATTERN = "Current Account"
FMP_COUNTRY = "NZ"

# Stats NZ BOP CSVシリーズID
BOP_SERIES_ID = "BOPQ.S06AC100000000D"

# 四半期末月マッピング（CSVのMM → 四半期）
QUARTER_END_MONTHS = {3, 6, 9, 12}

# 過去のリリースページURL（新しい順に試す）
RELEASE_PAGE_BASE = "https://www.stats.govt.nz/information-releases/balance-of-payments-and-international-investment-position-{quarter_name}-{year}-quarter"

QUARTER_NAMES = {
    3: "march",
    6: "june",
    9: "september",
    12: "december",
}


def _discover_csv_url() -> Optional[str]:
    """最新リリースページをスクレイピングしてCSV URLを発見"""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    now = datetime.now(JST)
    year = now.year
    month = now.month

    # 直近4四半期を試す
    quarter_months = [12, 9, 6, 3]
    current_qm = None
    for qm in quarter_months:
        if month >= qm:
            current_qm = qm
            break
    if current_qm is None:
        current_qm = 12
        year -= 1

    attempts = []
    y, qm = year, current_qm
    for _ in range(5):
        attempts.append((y, qm))
        idx = quarter_months.index(qm)
        if idx + 1 < len(quarter_months):
            qm = quarter_months[idx + 1]
        else:
            qm = quarter_months[0]
            y -= 1

    for y, qm in attempts:
        qname = QUARTER_NAMES[qm]
        url = RELEASE_PAGE_BASE.format(quarter_name=qname, year=y)
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                continue
            text = html.unescape(resp.text).replace("\\/", "/")
            # CSVへのリンクを探す（BOP CSV）
            links = re.findall(
                r"/assets/Uploads/Balance-of-payments/[^\"'<>\s]+\.csv",
                text,
            )
            for link in links:
                if "revisions" not in link.lower():
                    csv_url = f"https://www.stats.govt.nz{link}"
                    print(f"[NzCA] Discovered CSV URL: {csv_url}")
                    return csv_url
        except Exception as e:
            print(f"[NzCA] Error checking {qname} {y}: {e}")
            continue

    return None


def _parse_bop_csv(content: bytes) -> List[Dict[str, Any]]:
    """BOP CSVからCurrent Account Balanceを抽出"""
    try:
        text = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))

        records = {}
        for row in reader:
            series_ref = row.get("Series_reference", "").strip()
            if series_ref != BOP_SERIES_ID:
                continue

            period = row.get("Period", "").strip()
            data_value_str = row.get("Data_value", "").strip()
            magntude_str = row.get("MAGNTUDE", "").strip()

            if not period or not data_value_str or data_value_str in ("", "...", "C", "S", "P"):
                continue

            # 期間フォーマット: YYYY.MM
            parts = period.split(".")
            if len(parts) != 2:
                continue

            try:
                year = int(parts[0])
                month = int(parts[1])
            except ValueError:
                continue

            if month not in QUARTER_END_MONTHS:
                continue

            # 日付文字列 (四半期末月の1日)
            date_str = f"{year}-{month:02d}-01"

            try:
                value = float(data_value_str)
            except ValueError:
                continue

            # MAGNTUDE=6 → 百万NZD → /1000 で十億NZD
            try:
                magntude = int(magntude_str)
            except (ValueError, TypeError):
                magntude = 6  # デフォルト

            if magntude == 6:
                value_bn = round(value / 1000, 3)
            elif magntude == 9:
                value_bn = round(value, 3)
            else:
                value_bn = round(value / (10 ** (6 - magntude)) / 1000, 3)

            records[date_str] = value_bn

        if not records:
            print(f"[NzCA] No records found for series {BOP_SERIES_ID}")
            return []

        # 日付順にソート
        sorted_dates = sorted(records.keys())

        # QoQ増減幅を計算
        result = []
        for i, date_str in enumerate(sorted_dates):
            value = records[date_str]
            qoq_change = None
            if i > 0:
                prev_value = records[sorted_dates[i - 1]]
                qoq_change = round(value - prev_value, 3)

            result.append({
                "date": date_str,
                "value": value,
                "qoq_change": qoq_change,
            })

        print(f"[NzCA] Parsed {len(result)} records, range: {result[0]['date']} to {result[-1]['date']}")
        if result:
            latest = result[-1]
            print(f"[NzCA] Latest: {latest['date']} value={latest['value']}B NZD, qoq={latest.get('qoq_change')}")

        return result

    except Exception as e:
        print(f"[NzCA] Error parsing BOP CSV: {e}")
        import traceback
        traceback.print_exc()
        return []


class NzCurrentAccountBalanceService:
    """NZ 経常収支サービス（Stats NZ BOP CSV方式）"""

    DATA_CACHE_KEY = "newzealand:nz_current_account_balance:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """経常収支データを取得"""
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # Stats NZ BOP CSVからデータ取得
        data = self._load_from_stats_nz()

        if data:
            latest = data[-1] if data else None

            metadata = {
                "source": "Stats NZ",
                "indicator": "Balance of Payments - Current Account Balance",
                "series": BOP_SERIES_ID,
                "description": "NZ 経常収支（Current Account Balance）",
                "unit": "十億NZD",
                "frequency": "quarterly",
            }

            cache_payload = {
                "data": data,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": data,
                "latest": latest,
                "metadata": metadata,
                "next_release": next_release,
                "cached": False,
                "source": "stats_nz_csv",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
        }

    def _load_from_stats_nz(self) -> Optional[List[Dict[str, Any]]]:
        """Stats NZ BOP CSVをダウンロードしてパース"""
        csv_url = _discover_csv_url()
        if not csv_url:
            print("[NzCA] Failed to discover CSV URL")
            return None

        try:
            session = requests.Session()
            session.headers.update({"User-Agent": "Mozilla/5.0"})
            print(f"[NzCA] Downloading CSV: {csv_url}")
            resp = session.get(csv_url, timeout=120)
            if resp.status_code != 200 or len(resp.content) < 10000:
                print(f"[NzCA] Failed to download CSV: {resp.status_code}, size={len(resp.content)}")
                return None

            print(f"[NzCA] Downloaded CSV: {len(resp.content):,} bytes")
            return _parse_bop_csv(resp.content)

        except Exception as e:
            print(f"[NzCA] Error downloading CSV: {e}")
            return None

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            print(f"[NzCA] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_EVENT_PATTERN, last_updated_str, country=FMP_COUNTRY)
        except Exception:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                return (now - last_updated).total_seconds() > 86400
            except Exception:
                return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[NzCA] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[NzCA] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        next_release = self._get_next_release()

        data_count = 0
        if cached_data:
            data_count = len(cached_data.get("data", []))

        return {
            "indicator": "NZ Current Account Balance",
            "source": "Stats NZ BOP CSV",
            "series": BOP_SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": data_count,
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_current_account_balance_service = NzCurrentAccountBalanceService()
