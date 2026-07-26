"""
フランス企業信頼感サービス
INSEEのXLSファイルからFrance Business Confidenceデータを取得

指標:
- Business Confidence (企業信頼感)

データソース:
- INSEE XLS（主データソース）
  https://www.insee.fr/fr/statistiques/fichier/8730143/014_EMI_4.xls
- FMP（次回発表日時のみ）

発表スケジュール:
- 月次
- FMPカレンダーから取得

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import re
import requests
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Paris")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "france_business_confidence_cache.json"

# 長期履歴シード（Investing 518 = INSEE 製造業景況感, 1976-05〜。FMPが2025-04以降のみ
# しか保持しないため一度だけ手動投入した静的履歴。FMP実値と完全一致＝重複期間は無害。
# 将来分はFMPで自動更新され、本CSVは更新不要）。
SEED_CSV_PATH = (
    Path(__file__).parent.parent.parent / "data" / "csv_import" / "france_business_confidence.csv"
)

# INSEE XLS URL (公表ごとにファイル ID が変わり凍結するためフォールバック扱い)
INSEE_XLS_URL = "https://www.insee.fr/fr/statistiques/fichier/8730143/014_EMI_4.xls"

# INSEE BDM SDMX (安定): フランス企業景況感 統合指数 (climat des affaires France)
# idbank 001565530。ファイル ID 陳腐化の影響を受けず、最新月まで自動追従できる。
INSEE_BDM_URL = "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/001565530"


class FranceBusinessConfidenceService:
    """フランス企業信頼感サービス（INSEE XLS方式）"""

    DATA_CACHE_KEY = "eurozone:economy:france_business_confidence:data"
    ECONALPHA_ID = "france_business_confidence"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        フランス企業信頼感データを取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-01", "value": float, ...}, ...],
                "latest": {...},
                "metadata": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
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
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

            # ファイルキャッシュもチェック
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # 主ソース = FMP "Business Confidence"（FR）。
        # 旧実装は INSEE BDM 001565530（climat des affaires "全部門"）を取得していたが、
        # それは FMP/Trading Economics 等が言う "France Business Confidence" ではなく
        # 別系列（"Business Climate Indicator"）で、名称・FMPマッピング・発表日と不一致だった
        # (2026-06: 全部門94 vs Business Confidence 100)。名称どおりの系列に統一する。
        # 長期履歴シード（静的）＋ FMP（最新・将来分）をマージ。FMPが新しい月を上書き。
        merged: Dict[str, float] = {d["date"]: d["value"] for d in self._load_seed_csv()}
        for d in self._load_from_fmp():
            merged[d["date"]] = d["value"]
        fmp_result = [{"date": k, "value": v} for k, v in sorted(merged.items())]

        if fmp_result:
            latest = fmp_result[-1] if fmp_result else None
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "data": fmp_result,
                "latest": latest,
                "metadata": {
                    "source": "INSEE (via FMP) - France Business Confidence",
                    "country": "France",
                    "unit": "Index",
                    "frequency": "Monthly",
                    "description": "France Business Confidence（企業信頼感）",
                },
                "next_release": next_release,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": fmp_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "fmp",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
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
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    # 月略称 → 月番号（FMPラベル "(Jun)" 等の解析用）
    _MONTH_ABBR = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    def _parse_ref_month(self, label: str, release_dt: datetime) -> Optional[str]:
        """FMPイベントラベルの "(Jun)" 等から参照月 "YYYY-MM-01" を復元。

        France Business Confidence は当月分（"(Jun)" を6月に発表）。ラベル月が発表月より
        先行する場合（"(Dec)" を翌1月発表 等）は前年と判定する。
        """
        m = re.search(r"\(([A-Za-z]{3})\)", label or "")
        if not m:
            return None
        mon = self._MONTH_ABBR.get(m.group(1).lower())
        if not mon:
            return None
        year = release_dt.year
        if mon > release_dt.month + 1:
            year -= 1
        return f"{year:04d}-{mon:02d}-01"

    def _load_seed_csv(self) -> List[Dict[str, Any]]:
        """静的な長期履歴シード（date,value）を読み込む。存在しなければ空。"""
        result: List[Dict[str, Any]] = []
        try:
            if not SEED_CSV_PATH.exists():
                return result
            with open(SEED_CSV_PATH, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            for line in lines[1:]:  # ヘッダー(date,value)をスキップ
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 2:
                    continue
                date_str = parts[0].strip()
                try:
                    value = round(float(parts[1].strip()), 1)
                except (ValueError, TypeError):
                    continue
                if len(date_str) == 7:  # "YYYY-MM" 保険
                    date_str = f"{date_str}-01"
                result.append({"date": date_str, "value": value})
        except Exception as e:
            print(f"[FranceBusinessConfidence] Failed to load seed CSV: {e}")
        return result

    def _load_from_fmp(self) -> List[Dict[str, Any]]:
        """FMP "Business Confidence"（FR）を主ソースとして取得。

        - DB economic_calendar_events（カレンダー同期で蓄積）から actual を取得。
        - "Business Climate Indicator"（全部門景況感=別系列）は除外。
        - ラベル "(Mon)" から参照月を復元し、参照月ごとに最新（確報）を採用。
        - 直近はDB同期前の速報を取りこぼさないようライブFMP APIで補完。
        Returns: [{"date": "YYYY-MM-01", "value": float}, ...]（日付昇順）
        """
        by_month: Dict[str, float] = {}

        # 1. DB（高速・蓄積分）
        try:
            from core.database import get_db_connection
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT datetime_utc, event, actual
                    FROM economic_calendar_events
                    WHERE country = 'FR'
                      AND event ILIKE '%Business Confidence%'
                      AND event NOT ILIKE '%Climate%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                for dt_utc, event, actual in cur.fetchall():
                    ref = self._parse_ref_month(event, dt_utc)
                    if ref and actual is not None:
                        by_month[ref] = float(actual)  # 昇順なので後勝ち=確報
                cur.close()
        except Exception as e:
            print(f"[FranceBusinessConfidence] DB query failed: {e}")

        # 2. ライブFMP補完（直近90日。DB同期前の速報を即反映）
        try:
            from services.calendar.fmp_service import fmp_service
            from datetime import date as date_type, timedelta
            today = date_type.today()
            raw = fmp_service.fetch_calendar(today - timedelta(days=90), today, country="FR")
            for ev in raw:
                if ev.get("country") != "FR":
                    continue
                name = ev.get("event", "")
                if "business confidence" not in name.lower() or "climate" in name.lower():
                    continue
                if ev.get("actual") is None:
                    continue
                dt_utc, _ = fmp_service.parse_datetime(ev.get("date", ""))
                if not dt_utc:
                    continue
                ref = self._parse_ref_month(name, dt_utc)
                if ref:
                    by_month[ref] = float(ev["actual"])
        except Exception as e:
            print(f"[FranceBusinessConfidence] FMP live supplement failed: {e}")

        result = [{"date": d, "value": round(v, 1)} for d, v in sorted(by_month.items())]
        print(f"[FranceBusinessConfidence] Loaded {len(result)} records from FMP")
        return result

    def _load_from_insee_bdm(self) -> List[Dict[str, Any]]:
        """INSEE BDM SDMX API から企業景況感指数を取得 (安定ソース)。

        ファイル ID 陳腐化の影響を受けない。失敗時は空リストを返し、
        呼び出し側が従来の XLS にフォールバックする。
        Returns: [{"date": "YYYY-MM-01", "value": float}, ...] (日付昇順)
        """
        import xml.etree.ElementTree as ET
        try:
            print(f"[FranceBusinessConfidence] Fetching from INSEE BDM: {INSEE_BDM_URL}")
            resp = requests.get(
                INSEE_BDM_URL,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code != 200:
                print(f"[FranceBusinessConfidence] BDM HTTP {resp.status_code}")
                return []

            root = ET.fromstring(resp.content)
            result: List[Dict[str, Any]] = []
            for el in root.iter():
                if el.tag.split("}")[-1] != "Obs":
                    continue
                # generic SDMX: TIME_PERIOD/OBS_VALUE は属性または子要素
                period = el.get("TIME_PERIOD")
                value = el.get("OBS_VALUE")
                if period is None:
                    for c in el:
                        ct = c.tag.split("}")[-1]
                        if ct == "ObsDimension":
                            period = c.get("value")
                        elif ct == "ObsValue":
                            value = c.get("value")
                if not period or value in (None, ""):
                    continue
                # "YYYY-MM" -> "YYYY-MM-01"
                date_str = f"{period}-01" if len(period) == 7 else period
                try:
                    v = float(value)
                except (ValueError, TypeError):
                    continue
                if 0 < v < 300:
                    result.append({"date": date_str, "value": round(v, 1)})

            # 日付昇順 + 重複除去
            dedup = {r["date"]: r for r in sorted(result, key=lambda x: x["date"])}
            out = sorted(dedup.values(), key=lambda x: x["date"])
            print(f"[FranceBusinessConfidence] Loaded {len(out)} records from INSEE BDM")
            return out
        except Exception as e:
            print(f"[FranceBusinessConfidence] Error loading from INSEE BDM: {e}")
            return []

    def _load_from_insee_xls(self) -> List[Dict[str, Any]]:
        """INSEEのXLSファイルからデータを取得"""
        try:
            import pandas as pd

            print(f"[FranceBusinessConfidence] Fetching XLS from: {INSEE_XLS_URL}")

            response = requests.get(INSEE_XLS_URL, timeout=30)
            response.raise_for_status()

            # XLSをパース
            df = pd.read_excel(io.BytesIO(response.content), engine='xlrd', header=None)

            print(f"[FranceBusinessConfidence] XLS shape: {df.shape}")

            # INSEEのXLS構造を解析
            # 通常、最初の数行はヘッダー情報
            # データ行は日付（YYYY-MM形式）と値を含む

            result = []

            # 月名のフランス語/英語マッピング
            month_map_fr = {
                'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
                'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12,
                'janv': 1, 'févr': 2, 'avr': 4, 'juil': 7, 'sept': 9, 'oct': 10, 'nov': 11, 'déc': 12,
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }

            # データ開始行を探す
            data_start_row = 0
            date_col_idx = 0
            value_col_idx = 1

            # ヘッダー行を探してデータ構造を特定
            for idx in range(min(20, len(df))):
                row = df.iloc[idx]
                row_str = str(row.iloc[0]).lower() if not pd.isna(row.iloc[0]) else ""

                # 日付パターンを検出（YYYY-MM, MM-YYYY, 年月形式など）
                if any(year in row_str for year in ['1990', '1995', '2000', '2005', '2010', '2015', '2020']):
                    data_start_row = idx
                    break

                # 数値データの開始を検出
                try:
                    first_val = row.iloc[0]
                    if isinstance(first_val, (int, float)) and 1990 <= first_val <= 2030:
                        data_start_row = idx
                        break
                except:
                    pass

            print(f"[FranceBusinessConfidence] Data starts at row {data_start_row}")

            # データ行を処理
            for idx in range(data_start_row, len(df)):
                try:
                    row = df.iloc[idx]
                    date_val = row.iloc[date_col_idx]
                    value_val = row.iloc[value_col_idx] if len(row) > value_col_idx else None

                    if pd.isna(date_val):
                        continue

                    # 日付をパース
                    date_str = None

                    # datetime型の場合
                    if isinstance(date_val, datetime):
                        date_str = date_val.strftime("%Y-%m-01")
                    elif isinstance(date_val, str):
                        date_val_clean = date_val.strip()

                        # YYYY-MM形式
                        if len(date_val_clean) == 7 and '-' in date_val_clean:
                            try:
                                parts = date_val_clean.split('-')
                                if len(parts) == 2:
                                    if parts[0].isdigit() and len(parts[0]) == 4:
                                        # YYYY-MM形式
                                        date_str = f"{parts[0]}-{parts[1].zfill(2)}-01"
                                    elif parts[1].isdigit() and len(parts[1]) == 4:
                                        # MM-YYYY形式
                                        date_str = f"{parts[1]}-{parts[0].zfill(2)}-01"
                            except:
                                pass

                        # フランス語月名形式（例: "janvier 2020" または "2020 janvier"）
                        if not date_str:
                            date_val_lower = date_val_clean.lower()
                            for month_name, month_num in month_map_fr.items():
                                if month_name in date_val_lower:
                                    # 年を抽出
                                    import re
                                    year_match = re.search(r'(19|20)\d{2}', date_val_lower)
                                    if year_match:
                                        year = year_match.group(0)
                                        date_str = f"{year}-{month_num:02d}-01"
                                        break

                    # 数値型の年の場合（年だけの列がある可能性）
                    elif isinstance(date_val, (int, float)):
                        year = int(date_val)
                        if 1990 <= year <= 2030:
                            # 月の情報を別の列から取得する必要がある場合
                            # または年のみのデータの場合は1月とする
                            date_str = f"{year}-01-01"

                    if not date_str:
                        continue

                    # 値をパース
                    if pd.isna(value_val):
                        continue

                    try:
                        value = float(value_val)
                        # 妥当な範囲チェック（企業信頼感指数は通常50-150程度）
                        if 0 < value < 300:
                            result.append({
                                "date": date_str,
                                "value": round(value, 1),
                            })
                    except (ValueError, TypeError):
                        continue

                except Exception as row_error:
                    print(f"[FranceBusinessConfidence] Error processing row {idx}: {row_error}")
                    continue

            # 日付でソートして重複を除去
            result.sort(key=lambda x: x["date"])

            # 同じ日付のデータがあれば最新を保持
            seen_dates = {}
            for item in result:
                seen_dates[item["date"]] = item
            result = list(seen_dates.values())
            result.sort(key=lambda x: x["date"])

            print(f"[FranceBusinessConfidence] Loaded {len(result)} records from INSEE XLS")
            return result

        except Exception as e:
            print(f"[FranceBusinessConfidence] Error loading from INSEE XLS: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[FranceBusinessConfidence] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[FranceBusinessConfidence] Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"[FranceBusinessConfidence] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "France Business Confidence",
            "source": "INSEE XLS",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
france_business_confidence_service = FranceBusinessConfidenceService()
