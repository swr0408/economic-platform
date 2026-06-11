"""
台湾電気機器輸出サービス
DBから台湾電子零組件輸出データを取得し、YoY/MoMを計算

指標:
- Electrical Equipment Exports (Taiwan): 台湾電気機器輸出（電子零組件）

データソース:
- DB: economic_calendar_events（CSV過去データ）
- MOF (Ministry of Finance, Taiwan): 最新値Excel
  https://www.mof.gov.tw/download/21848 MajExシート (1)電子零組件

発表スケジュール:
- 毎月7~12日の間に16:00 UTC+8（= 17:00 JST）に更新

キャッシュ方式: 日次リフレッシュ（FMPマッピングなし）

注意事項:
- DBには百萬美元の原数値を保存
- YoY%、MoM%はサービス側で計算
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "taiwan_electrical_equipment_exports_cache.json"

# 旧 download/21848 は失効 (HTML を返す)。MOF は月次 Excel を ROC 年月で配信:
#   https://service.mof.gov.tw/public/Data/statistic/trade/news/{ROC_YYMM}/NET{ROC_YYMM}E.xlsx
#   ROC_YYMM = (西暦-1911)*100 + 月。英語版シート "MajXe" の "Parts of Electronic Product"
#   行 (col1=当月 US$M, col3=前年同月)。各ファイルは1ヶ月分。
MOF_NEWS_URL_TMPL = (
    "https://service.mof.gov.tw/public/Data/statistic/trade/news/{ym}/NET{ym}E.xlsx"
)
MAJXE_SHEET = "MajXe"
MAJXE_ROW_EN = "Parts of Electronic Product"

# 旧ソース (現在 dead、フォールバック用に残置)
MOF_EXCEL_URL = "https://www.mof.gov.tw/download/21848"
MAJEX_ROW_NAME = "(1)電子零組件"


class TaiwanElectricalEquipmentExportsService:
    """台湾電気機器輸出サービス"""

    DATA_CACHE_KEY = "global:taiwan_electrical_equipment_exports:data"

    # DBクエリ用のイベントパターン
    EVENT_PATTERNS = ["Electrical Equipment Exports"]

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """台湾電気機器輸出データを取得"""

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
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # DBから原数値を取得
        raw_data = self._load_from_db()

        # MOFの月次Excelから直近数ヶ月を取得してマージ (欠損月を埋める)
        for rec in self._fetch_recent_from_mof():
            raw_data = self._merge_mof_data(raw_data, rec)

        if raw_data:
            # YoY/MoMを計算
            processed_data = self._compute_yoy_mom(raw_data)
            latest = processed_data[-1] if processed_data else None

            metadata = {
                "source": "MOF (Ministry of Finance, Taiwan)",
                "indicator": "Taiwan Electrical Equipment Exports",
                "description": "台湾電気機器輸出（電子零組件）",
                "unit": "百萬美元",
                "frequency": "monthly",
            }

            cache_payload = {
                "data": processed_data,
                "latest": latest,
                "metadata": metadata,
                "next_release": None,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "database",
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
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
        }

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから原数値の履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                pattern_conditions = " OR ".join(
                    [f"event ILIKE :pattern{i}" for i in range(len(self.EVENT_PATTERNS))]
                )
                query = text(f"""
                    SELECT datetime_utc, event, actual
                    FROM economic_calendar_events
                    WHERE country = 'TW'
                      AND ({pattern_conditions})
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)

                params = {}
                for i, pattern in enumerate(self.EVENT_PATTERNS):
                    params[f"pattern{i}"] = f"%{pattern}%"

                rows = session.execute(query, params).fetchall()

                result = []
                for row in rows:
                    dt_utc, event, actual = row
                    if dt_utc:
                        # CSVインポートデータ: JST→UTC変換されているためJSTに戻す
                        dt_jst = dt_utc.astimezone(JST) if dt_utc.tzinfo else dt_utc.replace(tzinfo=UTC).astimezone(JST)
                        date_str = f"{dt_jst.year}-{dt_jst.month:02d}-01"

                        # 同一月は後のレコードで上書き
                        existing_idx = None
                        for i, existing in enumerate(result):
                            if existing["date"] == date_str:
                                existing_idx = i
                                break

                        data_point = {
                            "date": date_str,
                            "raw_value": float(actual) if actual else None,
                        }

                        if existing_idx is not None:
                            result[existing_idx] = data_point
                        else:
                            result.append(data_point)

                print(f"[TaiwanElectricalEquipmentExports] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            print(f"[TaiwanElectricalEquipmentExports] Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_recent_from_mof(self, months: int = 8) -> List[Dict[str, Any]]:
        """MOF 月次 Excel (NET{ROC_YYMM}E.xlsx, sheet MajXe) から直近数ヶ月の
        電子零組件輸出額を取得する。各ファイルは1ヶ月分で、月は URL の ROC_YYMM から
        確定する (シートのヘッダー解析不要)。存在しない月 (未公表) はスキップ。
        Returns: [{"current_date","current_value","prev_year_date","prev_year_value"}, ...]
        """
        import io
        import warnings
        import requests
        import pandas as pd
        warnings.filterwarnings("ignore")

        out: List[Dict[str, Any]] = []
        now = datetime.now(JST)
        for back in range(months):
            m = now.month - back
            yy = now.year
            while m <= 0:
                m += 12
                yy -= 1
            ym = (yy - 1911) * 100 + m  # ROC 年月
            url = MOF_NEWS_URL_TMPL.format(ym=ym)
            try:
                resp = requests.get(url, timeout=40, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200 or not resp.content[:4] == b"PK\x03\x04":
                    continue
                xls = pd.ExcelFile(io.BytesIO(resp.content))
                if MAJXE_SHEET not in xls.sheet_names:
                    continue
                df = pd.read_excel(xls, sheet_name=MAJXE_SHEET, header=None)
                target = None
                for ri in range(df.shape[0]):
                    cell = df.iloc[ri, 0]
                    if pd.notna(cell) and MAJXE_ROW_EN in str(cell):
                        target = ri
                        break
                if target is None:
                    continue
                cur = df.iloc[target, 1]   # col1 = 当月 (CY current)
                prev = df.iloc[target, 3]  # col3 = 前年同月 (CY prior)
                if pd.isna(cur):
                    continue
                rec = {
                    "current_date": f"{yy}-{m:02d}-01",
                    "current_value": float(cur),
                }
                if pd.notna(prev):
                    rec["prev_year_date"] = f"{yy - 1}-{m:02d}-01"
                    rec["prev_year_value"] = float(prev)
                out.append(rec)
            except Exception as e:
                print(f"[TaiwanElectricalEquipmentExports] MOF fetch error for {ym}: {e}")
                continue

        print(f"[TaiwanElectricalEquipmentExports] MOF fetched {len(out)} recent months")
        return out

    def _fetch_latest_from_mof(self) -> Optional[Dict[str, Any]]:
        """MOF Excelから最新値と前年同月値を取得（旧 download/21848 用・現在 dead）"""
        try:
            import requests
            import pandas as pd
            import io
            import warnings
            warnings.filterwarnings("ignore")

            resp = requests.get(
                MOF_EXCEL_URL,
                timeout=60,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code != 200:
                print(f"[TaiwanElectricalEquipmentExports] MOF download failed: {resp.status_code}")
                return None

            xls = pd.ExcelFile(io.BytesIO(resp.content))
            if "MajEx" not in xls.sheet_names:
                print("[TaiwanElectricalEquipmentExports] MajEx sheet not found")
                return None

            df = pd.read_excel(xls, sheet_name="MajEx", header=None)

            # Row3のヘッダーから対象年月を取得（例: "115年1月" = 2026年1月）
            header_cell = df.iloc[3, 1]  # Col1 = 当月ヘッダー
            prev_header_cell = df.iloc[3, 3]  # Col3 = 前年同月ヘッダー

            current_year, current_month = self._parse_roc_header(str(header_cell))
            prev_year, prev_month = self._parse_roc_header(str(prev_header_cell))

            if current_year is None or current_month is None:
                print(f"[TaiwanElectricalEquipmentExports] Failed to parse header: {header_cell}")
                return None

            # 電子零組件の行を検索
            target_row = None
            for row_idx in range(5, df.shape[0]):
                cell = df.iloc[row_idx, 0]
                if pd.notna(cell) and MAJEX_ROW_NAME in str(cell):
                    target_row = row_idx
                    break

            if target_row is None:
                print(f"[TaiwanElectricalEquipmentExports] Row '{MAJEX_ROW_NAME}' not found")
                return None

            # B列 (Col1) = 当月値、D列 (Col3) = 前年同月値
            current_value = df.iloc[target_row, 1]
            prev_year_value = df.iloc[target_row, 3]

            if pd.isna(current_value):
                print("[TaiwanElectricalEquipmentExports] Current value is NaN")
                return None

            result = {
                "current_date": f"{current_year}-{current_month:02d}-01",
                "current_value": float(current_value),
            }

            if pd.notna(prev_year_value) and prev_year is not None and prev_month is not None:
                result["prev_year_date"] = f"{prev_year}-{prev_month:02d}-01"
                result["prev_year_value"] = float(prev_year_value)

            print(f"[TaiwanElectricalEquipmentExports] MOF latest: {result['current_date']} = {result['current_value']}")
            return result

        except Exception as e:
            print(f"[TaiwanElectricalEquipmentExports] Error fetching from MOF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_roc_header(self, header: str) -> tuple:
        """ROCカレンダーヘッダーをパース（例: '115年1月' → (2026, 1)）"""
        import re
        match = re.search(r'(\d+)年(\d+)月', header)
        if match:
            roc_year = int(match.group(1))
            month = int(match.group(2))
            ad_year = roc_year + 1911
            return ad_year, month
        return None, None

    def _merge_mof_data(self, raw_data: List[Dict], mof_latest: Dict) -> List[Dict]:
        """MOFの最新データをマージ"""
        # 当月値をマージ
        current_date = mof_latest["current_date"]
        current_value = mof_latest["current_value"]

        existing_idx = None
        for i, item in enumerate(raw_data):
            if item["date"] == current_date:
                existing_idx = i
                break

        if existing_idx is not None:
            raw_data[existing_idx]["raw_value"] = current_value
        else:
            raw_data.append({"date": current_date, "raw_value": current_value})

        # 前年同月値をマージ（DBに無い場合のみ）
        if "prev_year_date" in mof_latest and "prev_year_value" in mof_latest:
            prev_date = mof_latest["prev_year_date"]
            prev_value = mof_latest["prev_year_value"]
            prev_exists = any(item["date"] == prev_date for item in raw_data)
            if not prev_exists:
                raw_data.append({"date": prev_date, "raw_value": prev_value})

        # 日付でソート
        raw_data.sort(key=lambda x: x["date"])
        return raw_data

    def _compute_yoy_mom(self, raw_data: List[Dict]) -> List[Dict]:
        """原数値からYoY%とMoM%を計算"""
        # dateをキーにした辞書を作成
        date_map = {item["date"]: item["raw_value"] for item in raw_data}

        result = []
        for i, item in enumerate(raw_data):
            date_str = item["date"]
            raw_value = item["raw_value"]

            if raw_value is None:
                continue

            # YoY計算: 12ヶ月前のデータ
            year = int(date_str[:4])
            month = int(date_str[5:7])
            prev_year_date = f"{year - 1}-{month:02d}-01"
            prev_year_value = date_map.get(prev_year_date)

            yoy = None
            if prev_year_value and prev_year_value > 0:
                yoy = round(((raw_value - prev_year_value) / prev_year_value) * 100, 1)

            # MoM計算: 1ヶ月前のデータ
            if month == 1:
                prev_month_date = f"{year - 1}-12-01"
            else:
                prev_month_date = f"{year}-{month - 1:02d}-01"
            prev_month_value = date_map.get(prev_month_date)

            mom = None
            if prev_month_value and prev_month_value > 0:
                mom = round(((raw_value - prev_month_value) / prev_month_value) * 100, 1)

            result.append({
                "date": date_str,
                "value": yoy,
                "mom": mom,
                "raw_value": raw_value,
            })

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（日次）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            # 最終更新から24時間経過していたら更新
            if (now - last_updated) > timedelta(hours=24):
                return True
            # 毎月7-12日の17:00 JST前後に更新される
            # 7日以降で最終更新が7日より前なら更新
            if now.day >= 7 and last_updated.day < 7 and now.month == last_updated.month:
                return True
            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[TaiwanElectricalEquipmentExports] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TaiwanElectricalEquipmentExports] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        data_count = 0
        latest_date = None
        if cached_data:
            data_count = len(cached_data.get("data", []))
            latest_date = cached_data.get("latest", {}).get("date") if cached_data.get("latest") else None

        return {
            "indicator": "Taiwan Electrical Equipment Exports",
            "source": "Database + MOF Excel",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "latest_date": latest_date,
            "data_count": data_count,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
taiwan_electrical_equipment_exports_service = TaiwanElectricalEquipmentExportsService()
