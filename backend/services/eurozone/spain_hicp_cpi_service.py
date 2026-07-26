"""
スペインHICP/CPIサービス
INE (Instituto Nacional de Estadística) Tempus3 JSON APIからデータを取得
DBに蓄積して差分更新方式

指標:
- CPI MoM (前月比) - IPC251855
- CPI YoY (前年比) - IPC251856
- Core CPI MoM (コア前月比) - IPC253989
- Core CPI YoY (コア前年比) - IPC253990
- HICP MoM (調和CPI前月比) - IPCA1886
- HICP YoY (調和CPI前年比) - IPCA1885

データソース:
- INE Tempus3 JSON API（主データソース）
  https://servicios.ine.es/wstempus/js/EN/DATOS_SERIE/{series_code}?nult=N
- FMP（次回発表日時のみ）

DB格納方式:
- 初回: CSVダウンロードで過去データを一括格納（import_spain_cpi_initial_data.py）
- 以降: APIから最新値を取得してDB積み上げ

発表スケジュール:
- 月次
- FMPカレンダーから取得

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from core.database import get_db_connection
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Madrid")

# キャッシュディレクトリ（ファイルキャッシュ用）
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "spain_hicp_cpi_cache.json"

# INE Tempus3 API シリーズコード
# 2026: INE が ECOICOP ver.2 へ移行し、旧系列 (IPC251855/856, IPC253989/990,
# IPCA1885/1886) は 2025-12 で停止した。ver.2 の新系列コードへ更新する。
# (取得ロジックは同一。DATOS_SERIE のコードのみ差し替え)
INE_SERIES = {
    "cpi_mom": "IPC290752",      # National. Overall index. Monthly change (ECOICOP v2)
    "cpi_yoy": "IPC290750",      # National. Overall index. Annual change (ECOICOP v2)
    "core_cpi_mom": "IPC292512", # Core inflation (excl unprocessed food & energy). Monthly change
    "core_cpi_yoy": "IPC292510", # Core inflation (excl unprocessed food & energy). Annual change
    "hicp_mom": "IPCA8092",      # National Total. Overall index. Monthly change (HICP, ECOICOP v2)
    "hicp_yoy": "IPCA8090",      # National Total. Overall index. Annual change (HICP, ECOICOP v2)
}

# APIエンドポイント
INE_API_BASE = "https://servicios.ine.es/wstempus/js/EN/DATOS_SERIE"


class SpainHICPCPIService:
    """スペインHICP/CPIサービス（DB積み上げ方式）"""

    DATA_CACHE_KEY = "eurozone:inflation:spain_hicp_cpi:data"
    ECONALPHA_ID = "spain_hicp_cpi"
    FMP_COUNTRY = "ES"
    FMP_EVENT_PATTERN = "HICP YoY"

    # 最新N期間を取得（差分更新用）
    UPDATE_PERIODS = 3

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        スペインHICP/CPIデータを取得

        Returns:
            {
                "cpi_mom": [...],
                "cpi_yoy": [...],
                "core_cpi_mom": [...],
                "core_cpi_yoy": [...],
                "hicp_mom": [...],
                "hicp_yoy": [...],
                "latest_cpi_yoy": {...},
                "latest_hicp_yoy": {...},
                "metadata": {...},
                "next_release": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_by_pattern(
                        self.FMP_EVENT_PATTERN,
                        country=self.FMP_COUNTRY
                    )
                    return {
                        "cpi_mom": cached_data.get("cpi_mom", []),
                        "cpi_yoy": cached_data.get("cpi_yoy", []),
                        "core_cpi_mom": cached_data.get("core_cpi_mom", []),
                        "core_cpi_yoy": cached_data.get("core_cpi_yoy", []),
                        "hicp_mom": cached_data.get("hicp_mom", []),
                        "hicp_yoy": cached_data.get("hicp_yoy", []),
                        "latest_cpi_yoy": cached_data.get("latest_cpi_yoy"),
                        "latest_hicp_yoy": cached_data.get("latest_hicp_yoy"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # APIから最新データを取得してDBに積み上げ
        self._update_from_api()

        # DBからデータを取得
        db_data = self._load_from_database()

        if db_data:
            next_release = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            )

            # 最新値を取得
            latest_cpi_yoy = db_data["cpi_yoy"][-1] if db_data["cpi_yoy"] else None
            latest_hicp_yoy = db_data["hicp_yoy"][-1] if db_data["hicp_yoy"] else None

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("cpi_yoy", "hicp_yoy"),
                _max_date_of(db_data["cpi_yoy"], db_data["hicp_yoy"]), now_str
            )
            cache_payload = {
                "cpi_mom": db_data["cpi_mom"],
                "cpi_yoy": db_data["cpi_yoy"],
                "core_cpi_mom": db_data["core_cpi_mom"],
                "core_cpi_yoy": db_data["core_cpi_yoy"],
                "hicp_mom": db_data["hicp_mom"],
                "hicp_yoy": db_data["hicp_yoy"],
                "latest_cpi_yoy": latest_cpi_yoy,
                "latest_hicp_yoy": latest_hicp_yoy,
                "metadata": {
                    "source": "INE (Instituto Nacional de Estadística) - Tempus3 API + DB",
                    "country": "Spain",
                    "unit": "%",
                    "frequency": "Monthly",
                    "description": "スペイン消費者物価指数 / 調和消費者物価指数",
                    "series_codes": INE_SERIES,
                },
                "next_release": next_release,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "cpi_mom": db_data["cpi_mom"],
                "cpi_yoy": db_data["cpi_yoy"],
                "core_cpi_mom": db_data["core_cpi_mom"],
                "core_cpi_yoy": db_data["core_cpi_yoy"],
                "hicp_mom": db_data["hicp_mom"],
                "hicp_yoy": db_data["hicp_yoy"],
                "latest_cpi_yoy": latest_cpi_yoy,
                "latest_hicp_yoy": latest_hicp_yoy,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            )
            return {
                "cpi_mom": file_cache.get("cpi_mom", []),
                "cpi_yoy": file_cache.get("cpi_yoy", []),
                "core_cpi_mom": file_cache.get("core_cpi_mom", []),
                "core_cpi_yoy": file_cache.get("core_cpi_yoy", []),
                "hicp_mom": file_cache.get("hicp_mom", []),
                "hicp_yoy": file_cache.get("hicp_yoy", []),
                "latest_cpi_yoy": file_cache.get("latest_cpi_yoy"),
                "latest_hicp_yoy": file_cache.get("latest_hicp_yoy"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "cpi_mom": [],
            "cpi_yoy": [],
            "core_cpi_mom": [],
            "core_cpi_yoy": [],
            "hicp_mom": [],
            "hicp_yoy": [],
            "latest_cpi_yoy": None,
            "latest_hicp_yoy": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_database(self) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """DBからデータを読み込み"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                sql = """
                    SELECT
                        date,
                        cpi_yoy,
                        cpi_mom,
                        core_cpi_yoy,
                        core_cpi_mom,
                        hicp_yoy,
                        hicp_mom
                    FROM spain_cpi_history
                    ORDER BY date ASC
                """

                cursor.execute(sql)
                rows = cursor.fetchall()
                cursor.close()

                result = {
                    "cpi_mom": [],
                    "cpi_yoy": [],
                    "core_cpi_mom": [],
                    "core_cpi_yoy": [],
                    "hicp_mom": [],
                    "hicp_yoy": [],
                }

                for row in rows:
                    date_str = row[0].strftime("%Y-%m-%d") if row[0] else None
                    if not date_str:
                        continue

                    if row[1] is not None:
                        result["cpi_yoy"].append({"date": date_str, "value": float(row[1])})
                    if row[2] is not None:
                        result["cpi_mom"].append({"date": date_str, "value": float(row[2])})
                    if row[3] is not None:
                        result["core_cpi_yoy"].append({"date": date_str, "value": float(row[3])})
                    if row[4] is not None:
                        result["core_cpi_mom"].append({"date": date_str, "value": float(row[4])})
                    if row[5] is not None:
                        result["hicp_yoy"].append({"date": date_str, "value": float(row[5])})
                    if row[6] is not None:
                        result["hicp_mom"].append({"date": date_str, "value": float(row[6])})

                print(f"[SpainHICPCPI] Loaded {len(rows)} records from database")
                return result

        except Exception as e:
            print(f"[SpainHICPCPI] Error loading from database: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _update_from_api(self) -> None:
        """INE APIから最新データを取得してDBに積み上げ"""
        print("[SpainHICPCPI] Fetching latest data from INE API...")

        # 各シリーズの最新データを取得
        api_data = {}
        for key, series_code in INE_SERIES.items():
            try:
                data = self._fetch_series_data(series_code, self.UPDATE_PERIODS)
                if data:
                    api_data[key] = data
                    print(f"[SpainHICPCPI] Fetched {len(data)} records for {key} ({series_code})")
            except Exception as e:
                print(f"[SpainHICPCPI] Error fetching {key} ({series_code}): {e}")

        if not api_data:
            print("[SpainHICPCPI] No data fetched from API")
            return

        # DBに積み上げ（UPSERT）
        self._upsert_to_database(api_data)

    def _fetch_series_data(self, series_code: str, nult: int = 3) -> List[Dict[str, Any]]:
        """
        INE APIから特定のシリーズデータを取得

        Args:
            series_code: INEシリーズコード（例: IPC251856）
            nult: 取得する最新N期間

        Returns:
            [{"date": "YYYY-MM-01", "value": float}, ...]
        """
        try:
            url = f"{INE_API_BASE}/{series_code}?nult={nult}"

            print(f"[SpainHICPCPI] Fetching: {url}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            }

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            json_data = response.json()

            # APIレスポンス形式: {"COD": "...", "Nombre": "...", "Data": [...]}
            # データは "Data" キー内にネストされている
            data_list = json_data.get("Data", []) if isinstance(json_data, dict) else json_data

            result = []
            for item in data_list:
                try:
                    year = item.get("Anyo")
                    # FK_Periodo は月番号（1-12）を直接表す
                    month = item.get("FK_Periodo")
                    value = item.get("Valor")

                    if year is None or value is None or month is None:
                        continue

                    # 月番号が1-12の範囲内か確認
                    if not (1 <= month <= 12):
                        continue

                    date_str = f"{year}-{month:02d}-01"

                    result.append({
                        "date": date_str,
                        "value": round(float(value), 2),
                    })

                except Exception as item_error:
                    print(f"[SpainHICPCPI] Error parsing item: {item_error}")
                    continue

            result.sort(key=lambda x: x["date"])
            return result

        except requests.exceptions.RequestException as e:
            print(f"[SpainHICPCPI] Request error for {series_code}: {e}")
            return []
        except (KeyError, ValueError, TypeError) as e:
            print(f"[SpainHICPCPI] Parse error for {series_code}: {e}")
            return []

    def _parse_period_to_month(self, period_name: str) -> Optional[int]:
        """INEの期間名を月番号に変換"""
        if not period_name:
            return None

        period_lower = period_name.strip().lower()

        month_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
        }

        if period_lower in month_map:
            return month_map[period_lower]

        if period_lower.startswith('m') and len(period_lower) == 3:
            try:
                return int(period_lower[1:])
            except ValueError:
                pass

        try:
            month = int(period_name)
            if 1 <= month <= 12:
                return month
        except ValueError:
            pass

        return None

    def _upsert_to_database(self, api_data: Dict[str, List[Dict]]) -> None:
        """APIから取得したデータをDBにUPSERT"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # 日付ごとにデータをマージ
                merged = {}
                for data_type, records in api_data.items():
                    for record in records:
                        date = record["date"]
                        if date not in merged:
                            merged[date] = {}
                        merged[date][data_type] = record["value"]

                insert_count = 0
                update_count = 0

                for date_str, values in merged.items():
                    sql = """
                        INSERT INTO spain_cpi_history (
                            date, cpi_yoy, cpi_mom, core_cpi_yoy, core_cpi_mom, hicp_yoy, hicp_mom, source
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, 'ine_api'
                        )
                        ON CONFLICT (date) DO UPDATE SET
                            cpi_yoy = COALESCE(EXCLUDED.cpi_yoy, spain_cpi_history.cpi_yoy),
                            cpi_mom = COALESCE(EXCLUDED.cpi_mom, spain_cpi_history.cpi_mom),
                            core_cpi_yoy = COALESCE(EXCLUDED.core_cpi_yoy, spain_cpi_history.core_cpi_yoy),
                            core_cpi_mom = COALESCE(EXCLUDED.core_cpi_mom, spain_cpi_history.core_cpi_mom),
                            hicp_yoy = COALESCE(EXCLUDED.hicp_yoy, spain_cpi_history.hicp_yoy),
                            hicp_mom = COALESCE(EXCLUDED.hicp_mom, spain_cpi_history.hicp_mom),
                            source = 'ine_api',
                            updated_at = NOW()
                        RETURNING (xmax = 0) AS inserted
                    """

                    cursor.execute(sql, (
                        date_str,
                        values.get("cpi_yoy"),
                        values.get("cpi_mom"),
                        values.get("core_cpi_yoy"),
                        values.get("core_cpi_mom"),
                        values.get("hicp_yoy"),
                        values.get("hicp_mom"),
                    ))

                    result = cursor.fetchone()
                    if result and result[0]:
                        insert_count += 1
                    else:
                        update_count += 1

                conn.commit()
                cursor.close()
                print(f"[SpainHICPCPI] DB upsert: {insert_count} inserted, {update_count} updated")

        except Exception as e:
            print(f"[SpainHICPCPI] Error upserting to database: {e}")
            import traceback
            traceback.print_exc()

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[SpainHICPCPI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[SpainHICPCPI] Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"[SpainHICPCPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        # DBのレコード数を取得
        db_count = 0
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM spain_cpi_history")
                db_count = cursor.fetchone()[0]
                cursor.close()
        except:
            pass

        return {
            "indicator": "Spain HICP / CPI",
            "source": "INE Tempus3 API + Database",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "cpi_yoy_count": len(cached_data.get("cpi_yoy", [])) if cached_data else 0,
            "hicp_yoy_count": len(cached_data.get("hicp_yoy", [])) if cached_data else 0,
            "latest_cpi_yoy": cached_data.get("latest_cpi_yoy") if cached_data else None,
            "latest_hicp_yoy": cached_data.get("latest_hicp_yoy") if cached_data else None,
            "next_release": get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "series_codes": INE_SERIES,
            "db_record_count": db_count,
        }


# シングルトンインスタンス
spain_hicp_cpi_service = SpainHICPCPIService()
