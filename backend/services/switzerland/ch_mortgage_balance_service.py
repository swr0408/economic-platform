"""
スイス住宅ローン残高サービス

SNB Data Portalから住宅ローン残高（国内・CHF建て・全銀行）を取得

データソース:
- SNB Data Portal: https://data.snb.ch/
- API: BSTA.SNB.MONA_U.BIL.AKT.HYP

発表スケジュール:
- 月次（Monthly banking statistics）- 20日以降の最初の営業日 09:00（チューリッヒ時間）

単位: CHF（億CHF単位に変換して表示）
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.switzerland.snb_calendar_service import get_snb_next_release


JST = ZoneInfo("Asia/Tokyo")
ZURICH = ZoneInfo("Europe/Zurich")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "ch_mortgage_balance_cache.json"


class CHMortgageBalanceService:
    """スイス住宅ローン残高サービス"""

    CACHE_KEY = "switzerland:ch_mortgage_balance:data"
    CACHE_TTL = 86400  # 24時間

    # SNB Data Portal API
    API_URL = (
        "https://data.snb.ch/api/warehouse/cube/BSTA.SNB.MONA_U.BIL.AKT.HYP/data/csv/en"
        "?dimSel=KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(I),WAEHRUNG(CHF),FAELLIGKEIT(T),BANKENGRUPPE(A40)"
        "&fromDate=2000-01"
    )

    def get_mortgage_balance_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """住宅ローン残高データを取得

        Args:
            force_refresh: Trueの場合、キャッシュを無視して再取得

        Returns:
            {
                "data": [...],
                "latest": {...},
                "metadata": {...},
                "next_release": str,
                "last_publishing_date": str,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached = self._get_cached_data()
            if cached:
                return cached

        # APIからデータ取得
        try:
            data = self._fetch_from_api()
            if data:
                self._save_to_cache(data)
                return data
        except Exception as e:
            print(f"[CHMortgageBalance] Error fetching from API: {e}")

        # フォールバック: ファイルキャッシュ
        file_cache = self._load_file_cache()
        if file_cache:
            file_cache["cached"] = True
            file_cache["cache_source"] = "file_fallback"
            return file_cache

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "last_publishing_date": None,
            "cached": False,
            "source": "SNB Data Portal",
            "last_updated": None,
            "error": "データを取得できませんでした"
        }

    def _fetch_from_api(self) -> Optional[Dict[str, Any]]:
        """SNB APIからデータを取得"""
        print(f"[CHMortgageBalance] Fetching from: {self.API_URL}")

        resp = requests.get(self.API_URL, timeout=60)
        resp.raise_for_status()

        # CSVをパース
        lines = resp.text.strip().split('\n')

        # ヘッダー情報を取得
        publishing_date = None
        for line in lines[:5]:
            if line.startswith('"PublishingDate"'):
                match = re.search(r'"(\d{4}-\d{2}-\d{2})', line)
                if match:
                    publishing_date = match.group(1)
                break

        # データ行を抽出（ヘッダー行以降）
        data_start = 0
        for i, line in enumerate(lines):
            if line.startswith('"Date"'):
                data_start = i + 1
                break

        data_points = []
        for line in lines[data_start:]:
            if not line.strip():
                continue

            parts = line.split(';')
            if len(parts) >= 7:
                date_str = parts[0].strip().strip('"')
                value_str = parts[6].strip().strip('"')

                try:
                    # "1987-12" -> "1987-12-01"
                    date = f"{date_str}-01"
                    # 値はCHF単位、億CHF単位に変換
                    value_chf = float(value_str)
                    value = value_chf / 100_000_000  # CHF -> 億CHF

                    data_points.append({
                        "date": date,
                        "value": round(value, 2),
                        "value_chf": round(value_chf, 2),
                    })
                except (ValueError, IndexError):
                    continue

        if not data_points:
            return None

        # 日付順にソート
        data_points.sort(key=lambda x: x["date"])

        # 前月比・前年比を計算
        self._calculate_changes(data_points)

        # 最新値
        latest = data_points[-1] if data_points else None

        # 次回発表日
        next_release = get_snb_next_release("monthly_banking_statistics")

        result = {
            "data": data_points,
            "latest": latest,
            "metadata": {
                "unit": "100 million CHF",
                "description": "Mortgage claims, domestic, CHF, all banks",
                "source_url": "https://data.snb.ch/en/topics/banken/cube/BSTA.SNB.MONA_U.BIL.AKT.HYP",
            },
            "next_release": next_release,
            "last_publishing_date": publishing_date,
            "cached": False,
            "source": "SNB Data Portal",
            "last_updated": datetime.now(JST).isoformat(),
        }

        return result

    def _calculate_changes(self, data_points: List[Dict]) -> None:
        """前月比・前年比を計算"""
        for i, item in enumerate(data_points):
            value = item.get("value")
            if value is None:
                continue

            # 前月比（MoM）
            if i > 0:
                prev_value = data_points[i - 1].get("value")
                if prev_value and prev_value != 0:
                    item["mom"] = round((value - prev_value) / prev_value * 100, 2)

            # 前年比（YoY）- 12ヶ月前
            if i >= 12:
                yoy_value = data_points[i - 12].get("value")
                if yoy_value and yoy_value != 0:
                    item["yoy"] = round((value - yoy_value) / yoy_value * 100, 2)

    def _get_cached_data(self) -> Optional[Dict[str, Any]]:
        """Redisキャッシュからデータを取得"""
        cached = redis_client.get(self.CACHE_KEY)
        if cached:
            # 更新チェック
            if not self._should_refresh(cached):
                cached["cached"] = True
                cached["cache_source"] = "redis"
                return cached
        return None

    def _should_refresh(self, cached_data: Dict) -> bool:
        """キャッシュを更新すべきか判定"""
        next_release = cached_data.get("next_release")
        if not next_release:
            return False

        try:
            # 次回発表日時をパース
            release_dt = datetime.strptime(next_release, "%Y-%m-%d %H:%M")
            release_dt = release_dt.replace(tzinfo=ZURICH)
            now = datetime.now(ZURICH)

            # 発表時刻を過ぎていたら更新
            if now > release_dt:
                print(f"[CHMortgageBalance] Release time passed, refreshing")
                return True

        except (ValueError, TypeError):
            pass

        return False

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        """キャッシュに保存"""
        redis_client.set(self.CACHE_KEY, data, expire=self.CACHE_TTL)
        self._save_file_cache(data)

    def _load_file_cache(self) -> Optional[Dict]:
        """ファイルキャッシュを読み込む"""
        try:
            if not CACHE_FILE.exists():
                return None
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CHMortgageBalance] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict) -> None:
        """ファイルキャッシュを保存"""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHMortgageBalance] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        cached = redis_client.get(self.CACHE_KEY)
        return {
            "indicator": "CH Mortgage Balance",
            "source": "SNB Data Portal",
            "cache_key": self.CACHE_KEY,
            "exists": cached is not None,
            "last_updated": cached.get("last_updated") if cached else None,
            "next_release": cached.get("next_release") if cached else None,
            "data_points": len(cached.get("data", [])) if cached else 0,
            "file_cache_exists": CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_mortgage_balance_service = CHMortgageBalanceService()
