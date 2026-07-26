"""
NZ 交易条件（Terms of Trade）サービス

指標:
- Terms of Trade Index（輸出価格/輸入価格指数比）
- Export Price Index（輸出価格指数）
- Import Price Index（輸入価格指数）

データソース:
- Stats NZ Overseas Trade Indexes (Prices) Excel
- https://www.stats.govt.nz/information-releases/?filters=Balance%20of%20payments&topicFiltersID=635
- Excelファイル: overseas-trade-indexes-{month}-{year}-quarter-provisional-prices.xlsx
- シート: Table 1.01
  - Col 0=Year, Col 1=Quarter
  - Index値: Col 2=輸出, Col 4=輸入, Col 6=交易条件（Merchandise）
  - QoQ%: 同列構成（Row 36開始）
  - YoY%: 同列構成（Row 54開始）

FMPマッピング:
- Terms of Trade QoQ (econalpha_id: nz_terms_of_trade)

発表スケジュール: 四半期
"""
import json
import io
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_terms_of_trade_cache.json"

# FMPパターン
FMP_EVENT_PATTERN = "Terms of Trade QoQ"
FMP_COUNTRY = "NZ"

# Stats NZ Excelダウンロードの四半期→月名マッピング
QUARTER_MONTHS = {
    3: ("March", "march"),
    6: ("June", "june"),
    9: ("September", "september"),
    12: ("December", "december"),
}

# Table 1.01 の列インデックス（0始まり）
COL_YEAR = 0
COL_QUARTER = 1
COL_MERCH_EXPORT = 2    # Merchandise Exports Price Index
COL_MERCH_IMPORT = 4    # Merchandise Imports Price Index
COL_TERMS_OF_TRADE = 6  # Terms of Trade Index

# 四半期文字列 → 月番号
QUARTER_STR_TO_MONTH = {
    "Mar": 3,
    "Jun": 6,
    "Sep": 9,
    "Dec": 12,
}


def _build_excel_url(year: int, quarter_month: int) -> str:
    """Stats NZ Overseas Trade Indexes Excel URLを生成"""
    month_cap, month_lower = QUARTER_MONTHS[quarter_month]
    return (
        f"https://www.stats.govt.nz/assets/Uploads/International-trade/"
        f"International-trade-{month_cap}-{year}-quarter/Download-data/"
        f"overseas-trade-indexes-{month_lower}-{year}-quarter-provisional-prices.xlsx"
    )


class NzTermsOfTradeService:
    """NZ 交易条件サービス（Stats NZ Excel方式）"""

    DATA_CACHE_KEY = "newzealand:nz_terms_of_trade:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """交易条件データを取得"""
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

        # Stats NZ Excelからデータ取得
        data = self._load_from_stats_nz()

        if data:
            latest = data[-1] if data else None
            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            if latest:
                print(f"[NzToT] Latest: {latest['date']} ToT={latest.get('terms_of_trade_qoq')}%")

            metadata = {
                "source": "Stats NZ",
                "indicator": "Overseas Trade Indexes - Terms of Trade",
                "description": "NZ交易条件（輸出価格指数/輸入価格指数）",
                "unit": "%",
                "frequency": "quarterly",
                "sheet": "Table 1.01",
            }

            cache_payload = {
                "data": data,
                "latest": latest,
                "metadata": metadata,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": data,
                "latest": latest,
                "metadata": metadata,
                "next_release": next_release,
                "cached": False,
                "source": "stats_nz_excel",
                "last_updated": last_updated,
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
        """Stats NZ ExcelからTable 1.01を取得してパース"""
        now = datetime.now(JST)
        attempts = self._get_quarter_attempts(now.year, now.month)

        df = None
        for year, qm in attempts:
            url = _build_excel_url(year, qm)
            print(f"[NzToT] Trying: {url}")
            try:
                resp = requests.get(url, timeout=120)
                if resp.status_code == 200 and len(resp.content) > 5000:
                    df = pd.read_excel(io.BytesIO(resp.content), sheet_name="Table 1.01", header=None)
                    month_cap, _ = QUARTER_MONTHS[qm]
                    print(f"[NzToT] Downloaded {month_cap} {year} ({df.shape})")
                    break
            except Exception as e:
                print(f"[NzToT] Error downloading {year} Q{qm}: {e}")
                continue

        if df is None:
            print("[NzToT] Failed to download Excel")
            return None

        try:
            return self._parse_table_101(df)
        except Exception as e:
            print(f"[NzToT] Error parsing Excel: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_table_101(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Table 1.01をパースして3系列（輸出価格・輸入価格・交易条件）のQoQ%を返す

        シート構造:
          Row 8   : Quarterヘッダー（Indexセクション）
          Row 10~ : Index値（col 0=Year, col 1=Quarter, col 2=輸出, col 4=輸入, col 6=交易条件）
          Row 32  : "Percentage change from previous quarter" ヘッダー
          Row 34  : Quarterヘッダー（QoQセクション）
          Row 36~ : QoQ%値（同列構成）
          Row 50  : "Percentage change from same quarter of previous year" ヘッダー
          Row 52  : Quarterヘッダー（YoYセクション）
          Row 54~ : YoY%値（同列構成）

        NOTE: Year値は行が変わる際にのみ存在する（非空）
        """
        def _extract_section(start_row: int, end_row: int) -> Dict[str, Dict[str, Optional[float]]]:
            """指定行範囲からYear/Quarter別に数値を抽出"""
            result = {}
            current_year = None
            for r in range(start_row, min(end_row, df.shape[0])):
                year_val = df.iloc[r, COL_YEAR]
                quarter_val = df.iloc[r, COL_QUARTER]

                if pd.notna(year_val) and str(year_val).strip().isdigit():
                    current_year = int(str(year_val).strip())

                if current_year is None:
                    continue

                quarter_str = str(quarter_val).strip() if pd.notna(quarter_val) else ""
                if quarter_str not in QUARTER_STR_TO_MONTH:
                    continue

                # 日付を構築（Quarter終月の1日）
                month = QUARTER_STR_TO_MONTH[quarter_str]
                date_str = f"{current_year}-{month:02d}-01"

                def _safe_float(col: int) -> Optional[float]:
                    v = df.iloc[r, col]
                    if pd.isna(v):
                        return None
                    try:
                        return round(float(str(v).strip()), 2)
                    except (ValueError, TypeError):
                        return None

                result[date_str] = {
                    "export_price": _safe_float(COL_MERCH_EXPORT),
                    "import_price": _safe_float(COL_MERCH_IMPORT),
                    "terms_of_trade": _safe_float(COL_TERMS_OF_TRADE),
                }

            return result

        # QoQ%セクション（Row 36~48）
        qoq_data = _extract_section(36, 50)
        # YoY%セクション（Row 54~63）
        yoy_data = _extract_section(54, 65)

        # 全日付を統合
        all_dates = sorted(set(list(qoq_data.keys()) + list(yoy_data.keys())))

        result = []
        for date_str in all_dates:
            qoq = qoq_data.get(date_str, {})
            yoy = yoy_data.get(date_str, {})

            # 少なくとも1つの値があれば追加
            if any(v is not None for v in list(qoq.values()) + list(yoy.values())):
                result.append({
                    "date": date_str,
                    "terms_of_trade_qoq": qoq.get("terms_of_trade"),
                    "export_price_qoq": qoq.get("export_price"),
                    "import_price_qoq": qoq.get("import_price"),
                    "terms_of_trade_yoy": yoy.get("terms_of_trade"),
                    "export_price_yoy": yoy.get("export_price"),
                    "import_price_yoy": yoy.get("import_price"),
                })

        print(f"[NzToT] Parsed {len(result)} records, range: {result[0]['date'] if result else 'N/A'} to {result[-1]['date'] if result else 'N/A'}")
        return result

    def _get_quarter_attempts(self, year: int, month: int) -> List[tuple]:
        """ダウンロード試行する四半期リスト（最新から3四半期分）"""
        quarter_months = [12, 9, 6, 3]
        attempts = []

        current_qm = None
        for qm in quarter_months:
            if month >= qm:
                current_qm = qm
                break
        if current_qm is None:
            current_qm = 12
            year -= 1

        y, qm = year, current_qm
        for _ in range(4):
            attempts.append((y, qm))
            idx = quarter_months.index(qm)
            if idx + 1 < len(quarter_months):
                qm = quarter_months[idx + 1]
            else:
                qm = quarter_months[0]
                y -= 1

        return attempts

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            print(f"[NzToT] Error getting next release: {e}")
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
            print(f"[NzToT] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[NzToT] Failed to save file cache: {e}")

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
            "indicator": "NZ Terms of Trade (Overseas Trade Indexes)",
            "source": "Stats NZ Excel",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": data_count,
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_terms_of_trade_service = NzTermsOfTradeService()
