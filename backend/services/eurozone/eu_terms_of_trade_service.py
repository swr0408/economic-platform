"""
EU交易条件サービス
Eurostat APIから輸出・輸入単価指数データを取得し、交易条件を計算

指標:
- Terms of Trade (交易条件): 輸出単価指数 / 輸入単価指数 × 100
- Export Unit Value (輸出単価指数)
- Import Unit Value (輸入単価指数)

データソース:
- Eurostat API
  - ext_st_easitc: Euro area trade by SITC product group（ユーロ圏SITC別貿易）
    - indic_et=IVU: Unit value index (2021=100)（輸出入の単価指数）
    - 2002-01からの長期月次履歴を保持（短期テーブル teiet300/teiet310 は直近約1年のみ）
- Series Parameters (path series key: freq.stk_flow.indic_et.partner.sitc06.geo):
  - freq: M (Monthly)
  - stk_flow: EXP / IMP
  - indic_et: IVU (Unit value index, 2021=100)
  - partner: EXT_EA21 (Extra-euro area - 21 countries)
  - sitc06: TOTAL
  - geo: EA21 (2026-01にブルガリアがユーロ導入しEA20→EA21へ移行)

発表スケジュール:
- 月次（EU国際貿易と同時発表）
- FMPカレンダーから次回発表日を取得

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eu_terms_of_trade_cache.json"


class EUTermsOfTradeService:
    """EU交易条件サービス（Eurostat API）"""

    # Eurostat API base URL
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"

    # Dataset code（長期月次履歴を持つ完全データセット）
    # 旧 teiet300/teiet310（tei短期テーブル）は直近約1年しか保持しないため、
    # 元データセット ext_st_easitc の単価指数(IVU)へ移行し2002-01からの履歴を取得する。
    DATASET = "ext_st_easitc"

    # パスキー（dims順: freq.stk_flow.indic_et.partner.sitc06.geo）
    # partner=EXT_EA21（域外）, geo=EA21, indic_et=IVU（単価指数 2021=100）
    EXPORT_SERIES_KEY = "M.EXP.IVU.EXT_EA21.TOTAL.EA21"
    IMPORT_SERIES_KEY = "M.IMP.IVU.EXT_EA21.TOTAL.EA21"

    DATA_CACHE_KEY = "economy:eu_terms_of_trade:data"
    # EU国際貿易と同時発表のためマッピングを共用
    ECONALPHA_ID = "eu_international_trade"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        EU交易条件データを取得

        Returns:
            {
                "terms_of_trade": [...],     # 交易条件データ
                "export_uv": [...],          # 輸出単価指数データ
                "import_uv": [...],          # 輸入単価指数データ
                "latest_tot": {...},
                "latest_export_uv": {...},
                "latest_import_uv": {...},
                "metadata": {...},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        **{k: v for k, v in cached_data.items() if k != "last_updated"},
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        **{k: v for k, v in file_cache.items() if k != "last_updated"},
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # Eurostat APIから各指標を取得
        export_uv_data = self._fetch_eurostat_data(self.EXPORT_SERIES_KEY) or []
        import_uv_data = self._fetch_eurostat_data(self.IMPORT_SERIES_KEY) or []

        if export_uv_data and import_uv_data:
            # 交易条件を計算: (輸出単価指数 / 輸入単価指数) × 100
            terms_of_trade = self._calculate_terms_of_trade(export_uv_data, import_uv_data)

            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest_tot = terms_of_trade[-1] if terms_of_trade else None
            latest_export_uv = export_uv_data[-1] if export_uv_data else None
            latest_import_uv = import_uv_data[-1] if import_uv_data else None

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("terms_of_trade", "export_uv", "import_uv"),
                _max_date_of(terms_of_trade, export_uv_data, import_uv_data), now_str
            )
            cache_payload = {
                "terms_of_trade": terms_of_trade,
                "export_uv": export_uv_data,
                "import_uv": import_uv_data,
                "latest_tot": latest_tot,
                "latest_export_uv": latest_export_uv,
                "latest_import_uv": latest_import_uv,
                "metadata": {
                    "source": "Eurostat - External Trade",
                    "dataset": self.DATASET,
                    "export_series": self.EXPORT_SERIES_KEY,
                    "import_series": self.IMPORT_SERIES_KEY,
                    "area": "Euro area (21 countries)",
                    "unit": "Index (2021 = 100)",
                    "frequency": "Monthly",
                    "description": "Terms of Trade = Export Unit Value / Import Unit Value × 100",
                },
                "next_release": next_release,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "eurostat_api",
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                **file_cache,
                "cached": True,
                "source": "file (fallback)",
            }

        return {
            "terms_of_trade": [],
            "export_uv": [],
            "import_uv": [],
            "latest_tot": None,
            "latest_export_uv": None,
            "latest_import_uv": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _calculate_terms_of_trade(
        self, export_data: List[Dict], import_data: List[Dict]
    ) -> List[Dict]:
        """交易条件を計算: (輸出単価 / 輸入単価) × 100"""
        # 日付をキーにしたマップを作成
        import_map = {item["date"]: item["value"] for item in import_data}

        result = []
        for exp_item in export_data:
            date = exp_item["date"]
            exp_value = exp_item["value"]
            imp_value = import_map.get(date)

            if exp_value is not None and imp_value is not None and imp_value != 0:
                tot = (exp_value / imp_value) * 100
                result.append({
                    "date": date,
                    "value": round(tot, 2)
                })

        return result

    def _fetch_eurostat_data(self, series_key: str, start_period: str = "2002-01") -> Optional[List[Dict]]:
        """
        Eurostat APIから単一系列（パスキー指定）を取得

        Args:
            series_key: パスキー freq.stk_flow.indic_et.partner.sitc06.geo
                        (例: M.EXP.IVU.EXT_EA21.TOTAL.EA21)
            start_period: 開始期間 (YYYY-MM)。ext_st_easitc は 2002-01 から保持

        Returns:
            データポイントのリスト
        """
        # 注意: Eurostat SDMX 2.1 APIはフィルタをクエリパラメータではなくURLパスの
        # 系列キーで指定する必要がある（クエリ指定は無視され全キューブ取得→413になる）。
        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}/{series_key}"

        params = {
            "format": "JSON",
            "startPeriod": start_period,
        }

        try:
            print(f"[EUTermsOfTrade] Fetching {self.DATASET}/{series_key} from Eurostat API")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract dimensions and values
            dimensions = data.get("dimension", {})
            time_dim = dimensions.get("time", {})
            time_category = time_dim.get("category", {})
            time_index = time_category.get("index", {})

            values = data.get("value", {})

            if not time_index or not values:
                print(f"[EUTermsOfTrade] No data found for {series_key}")
                return None

            # Create index to time mapping
            idx_to_time = {v: k for k, v in time_index.items()}

            # Build result list
            result = []
            for val_idx_str in sorted(values.keys(), key=lambda x: int(x)):
                val_idx = int(val_idx_str)
                time_period = idx_to_time.get(val_idx)
                value = values.get(val_idx_str)

                if time_period and value is not None:
                    # Convert YYYY-MM to YYYY-MM-01
                    date_str = f"{time_period}-01"
                    result.append({
                        "date": date_str,
                        "value": float(value)
                    })

            print(f"[EUTermsOfTrade] Successfully fetched {len(result)} {series_key} data points")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[EUTermsOfTrade] API request error for {series_key}: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[EUTermsOfTrade] Data parsing error for {series_key}: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[EUTermsOfTrade] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EUTermsOfTrade] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "EU Terms of Trade",
            "source": "Eurostat API (teiet300, teiet310)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "tot_count": len(cached_data.get("terms_of_trade", [])) if cached_data else 0,
            "latest_tot": cached_data.get("latest_tot") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
eu_terms_of_trade_service = EUTermsOfTradeService()
