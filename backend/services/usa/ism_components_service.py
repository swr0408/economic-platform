"""
ISM製造業サブインデックスサービス
DBnomics APIからISM製造業の構成要素データを取得

データソース:
- DBnomics: https://db.nomics.world/ISM
- 新規受注: ISM/neword/in
- 生産: ISM/production/in
- 雇用: ISM/employment/in
- サプライヤー配送: ISM/supdel/in
- 価格（仕入価格）: ISM/prices/in
- 在庫: ISM/inventories/in

発表スケジュール:
- 毎月第1営業日付近（ISM製造業景況指数と同時）
- ISM製造業景況指数の発表スケジュールを共有

キャッシュ方式: last_updated判定方式
- ISM製造業景況指数の次回発表日で判定
"""
import csv
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# DBnomics API設定
DBNOMICS_BASE_URL = "https://api.db.nomics.world/v22"

# 手動更新CSV
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "monthly" / "ism_components"
CSV_FILE = CSV_DIR / "ism_manufacturing_components.csv"

# ISMサブインデックスのシリーズコード
ISM_SERIES = {
    "new_orders": "ISM/neword/in",
    "production": "ISM/production/in",
    "employment": "ISM/employment/in",
    "supplier_deliveries": "ISM/supdel/in",
    "prices": "ISM/prices/in",
    "inventories": "ISM/inventories/in",
}


class ISMComponentsService:
    """ISM製造業サブインデックスサービス"""

    CACHE_KEY = "dbnomics:ism_components"
    ECONALPHA_ID = "ism_manufacturing"  # FMPマッピング用ID

    def __init__(self):
        pass

    def get_ism_components_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ISM製造業サブインデックスデータを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [
                    {
                        "date": "YYYY-MM-01",
                        "new_orders": float,
                        "production": float,
                        "employment": float,
                        "supplier_deliveries": float,
                        "prices": float,
                        "inventories": float
                    },
                    ...
                ],
                "latest": {...},
                "next_release": {...} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                # last_updated判定: ISM製造業の発表日を過ぎていたらキャッシュ無効
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # DBnomics APIから取得
        fetched_result = self._fetch_from_dbnomics()

        if fetched_result and fetched_result.get("data"):
            # 成功 → DBに保存（派生フィールドを除いた基礎データ）
            self._save_to_db(fetched_result["data"], source="dbnomics")
        else:
            # 失敗 → DBからフォールバック読み込み
            print("DBnomics failed, falling back to DB...")
            db_data = self._load_from_db()
            if db_data:
                fetched_result = {"data": db_data}
                print(f"  Loaded {len(db_data)} records from DB")

        # DBnomicsデータをFMP DBの最新データで補完
        if fetched_result and fetched_result.get("data"):
            fetched_result["data"] = self._supplement_from_fmp_db(fetched_result["data"])
            # FMPで取得できた値をCSVに自動書き込み
            self._write_fmp_to_csv(fetched_result["data"])

        # CSVデータで補完（最優先）
        if fetched_result and fetched_result.get("data"):
            fetched_result["data"] = self._supplement_from_csv(fetched_result["data"])
            # CSV分もDBに保存
            self._save_csv_to_db(fetched_result["data"])
            fetched_result["data"] = self._recalculate_derived_fields(fetched_result["data"])

        if fetched_result and fetched_result.get("data"):
            fetched_data = fetched_result["data"]

            # 日付でソート（昇順）
            fetched_data.sort(key=lambda x: x["date"])

            # 最新値を取得
            latest = fetched_data[-1] if fetched_data else None

            cache_payload = {
                "data": fetched_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat(),
                "csv_mtime": self._get_csv_mtime(),
            }
            # last_updated方式: TTL=0（無期限、発表日判定で無効化）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": fetched_data,
                "latest": latest,
                "next_release": None,
                "cached": False,
                "source": "dbnomics",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        FMPスケジュールベースの判定 OR CSVファイルの更新検知
        """
        if should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str):
            return True

        # CSVファイルのタイムスタンプが変わっていればリフレッシュ
        cached_data = redis_client.get(self.CACHE_KEY)
        if cached_data:
            cached_csv_mtime = cached_data.get("csv_mtime")
            current_csv_mtime = self._get_csv_mtime()
            if cached_csv_mtime != current_csv_mtime:
                return True

        return False

    def _get_csv_mtime(self) -> Optional[str]:
        """CSVファイルの最終更新時刻を取得"""
        try:
            if CSV_FILE.exists():
                mtime = os.path.getmtime(CSV_FILE)
                return datetime.fromtimestamp(mtime, tz=JST).isoformat()
        except Exception:
            pass
        return None

    def _fetch_from_dbnomics(self) -> Optional[Dict[str, Any]]:
        """DBnomics APIからISMサブインデックスデータを取得"""
        try:
            print("Fetching ISM Components from DBnomics...")

            # 全シリーズを順次取得
            series_data = {}

            for name, series_code in ISM_SERIES.items():
                try:
                    url = f"{DBNOMICS_BASE_URL}/series/{series_code}?observations=1&format=json"
                    response = requests.get(url, timeout=30)
                    response.raise_for_status()
                    data = response.json()

                    # データを抽出
                    extracted = self._extract_series_data(data)
                    if extracted:
                        series_data[name] = extracted
                        print(f"  {name}: {len(extracted)} records")
                except Exception as e:
                    print(f"  Error fetching {name}: {e}")
                    continue

            if not series_data:
                print("No data fetched from DBnomics")
                return None

            # データを統合
            combined_data = self._combine_series_data(series_data)

            if combined_data:
                print(f"Combined {len(combined_data)} ISM Components records")
                return {"data": combined_data}

            return None

        except Exception as e:
            print(f"Error fetching ISM Components from DBnomics: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_series_data(self, data: Dict) -> Optional[List[Dict[str, Any]]]:
        """DBnomicsレスポンスからシリーズデータを抽出"""
        try:
            if not data or not isinstance(data, dict):
                return None

            series = data.get("series", {})
            if not series:
                return None

            docs = series.get("docs", [])
            if not docs or not isinstance(docs, list):
                return None

            doc = docs[0]
            periods = doc.get("period", [])
            values = doc.get("value", [])

            if not periods or not values or len(periods) != len(values):
                return None

            result = []
            for i, period in enumerate(periods):
                value = values[i]
                if value is not None and not (isinstance(value, float) and value != value):  # NaN check
                    result.append({
                        "period": str(period),
                        "value": float(value)
                    })

            return result

        except Exception as e:
            print(f"Error extracting series data: {e}")
            return None

    def _combine_series_data(self, series_data: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
        """複数シリーズのデータを期間ごとに統合し、受注在庫バランスを計算"""
        try:
            # 期間をキーにしてデータを統合
            combined = {}

            for series_name, data_points in series_data.items():
                for point in data_points:
                    period = point["period"]
                    value = point["value"]

                    if period not in combined:
                        combined[period] = {
                            "date": f"{period}-01",  # YYYY-MM → YYYY-MM-01
                        }

                    combined[period][series_name] = value

            # 全項目が揃っているレコードのみを返す
            result = []
            required_fields = ["new_orders", "inventories"]  # 受注在庫バランス計算に必須

            for period, data in combined.items():
                # 少なくとも受注と在庫が揃っているか確認
                if all(field in data for field in required_fields):
                    new_orders = data.get("new_orders")
                    inventories = data.get("inventories")

                    # 受注在庫バランスを計算
                    order_inventory_balance = None
                    if new_orders is not None and inventories is not None:
                        order_inventory_balance = round(new_orders - inventories, 1)

                    full_data = {
                        "date": data["date"],
                        "new_orders": new_orders,
                        "production": data.get("production"),
                        "employment": data.get("employment"),
                        "supplier_deliveries": data.get("supplier_deliveries"),
                        "prices": data.get("prices"),
                        "inventories": inventories,
                        "order_inventory_balance": order_inventory_balance,
                    }
                    result.append(full_data)

            # 日付でソート
            result = sorted(result, key=lambda x: x["date"])

            # 3ヶ月移動平均を計算
            for i, item in enumerate(result):
                if i >= 2:
                    # 直近3ヶ月の受注在庫バランスの平均
                    balances = [
                        result[i - 2].get("order_inventory_balance"),
                        result[i - 1].get("order_inventory_balance"),
                        item.get("order_inventory_balance"),
                    ]
                    if all(b is not None for b in balances):
                        item["order_inventory_balance_3ma"] = round(sum(balances) / 3, 1)
                    else:
                        item["order_inventory_balance_3ma"] = None
                else:
                    item["order_inventory_balance_3ma"] = None

            return result

        except Exception as e:
            print(f"Error combining series data: {e}")
            return []

    def _supplement_from_csv(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        CSVファイルから手動更新データを読み込んでマージ

        CSVの値はDBnomics/FMP DBの値を上書きする（最高優先度）。
        CSVで空欄のフィールドは既存値を保持する。
        """
        try:
            if not CSV_FILE.exists():
                return data

            csv_data = {}
            with open(CSV_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get("date", "").strip()
                    if not date_str:
                        continue

                    # 日付パース: "YYYY/M" -> "YYYY-MM-01"
                    try:
                        parts = date_str.split("/")
                        year = int(parts[0])
                        month = int(parts[1])
                        date_formatted = f"{year}-{month:02d}-01"
                    except (ValueError, IndexError):
                        continue

                    csv_data[date_formatted] = {}
                    for field in ["new_orders", "production", "employment",
                                  "supplier_deliveries", "prices", "inventories"]:
                        val_str = row.get(field, "").strip()
                        if val_str:
                            try:
                                csv_data[date_formatted][field] = float(val_str)
                            except ValueError:
                                pass

            if not csv_data:
                return data

            # 既存データをdate->indexマップに変換
            date_index = {item["date"]: i for i, item in enumerate(data)}

            for date_key, csv_fields in csv_data.items():
                if date_key in date_index:
                    # 既存月: CSVの値で上書き（空欄フィールドは保持）
                    idx = date_index[date_key]
                    for field, value in csv_fields.items():
                        data[idx][field] = value
                    print(f"  CSV override: {date_key} fields={list(csv_fields.keys())}")
                else:
                    # 新しい月: エントリ追加
                    entry = {
                        "date": date_key,
                        "new_orders": csv_fields.get("new_orders"),
                        "production": csv_fields.get("production"),
                        "employment": csv_fields.get("employment"),
                        "supplier_deliveries": csv_fields.get("supplier_deliveries"),
                        "prices": csv_fields.get("prices"),
                        "inventories": csv_fields.get("inventories"),
                        "order_inventory_balance": None,
                        "order_inventory_balance_3ma": None,
                    }
                    data.append(entry)
                    print(f"  CSV supplement: {date_key} fields={list(csv_fields.keys())}")

            data.sort(key=lambda x: x["date"])
            return data

        except Exception as e:
            print(f"Error supplementing from CSV: {e}")
            return data

    def _recalculate_derived_fields(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """受注在庫バランスと3ヶ月移動平均を再計算"""
        for item in data:
            new_orders = item.get("new_orders")
            inventories = item.get("inventories")
            if new_orders is not None and inventories is not None:
                item["order_inventory_balance"] = round(new_orders - inventories, 1)
            else:
                item["order_inventory_balance"] = None

        for i, item in enumerate(data):
            if i >= 2:
                balances = [
                    data[i - 2].get("order_inventory_balance"),
                    data[i - 1].get("order_inventory_balance"),
                    item.get("order_inventory_balance"),
                ]
                if all(b is not None for b in balances):
                    item["order_inventory_balance_3ma"] = round(sum(balances) / 3, 1)
                else:
                    item["order_inventory_balance_3ma"] = None
            else:
                item["order_inventory_balance_3ma"] = None

        return data

    def _save_to_db(self, data: List[Dict[str, Any]], source: str = "dbnomics") -> None:
        """基礎データをDBに保存（派生フィールドは除外）"""
        try:
            from services.usa.ism_components_db_utils import upsert_ism_components
            count = upsert_ism_components("manufacturing", data, source=source)
            if count > 0:
                print(f"  Saved {count} records to DB (source={source})")
        except Exception as e:
            print(f"  DB save failed: {e}")

    def _save_csv_to_db(self, data: List[Dict[str, Any]]) -> None:
        """CSVで補完されたデータのうち、CSV由来の月のみDBに保存"""
        try:
            if not CSV_FILE.exists():
                return

            # CSVの日付一覧を取得
            csv_dates = set()
            with open(CSV_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get("date", "").strip()
                    if date_str:
                        parts = date_str.split("/")
                        csv_dates.add(f"{int(parts[0])}-{int(parts[1]):02d}-01")

            if not csv_dates:
                return

            # CSV由来の月だけ抽出してDBに保存
            csv_records = [item for item in data if item.get("date") in csv_dates]
            if csv_records:
                from services.usa.ism_components_db_utils import upsert_ism_components
                count = upsert_ism_components("manufacturing", csv_records, source="csv")
                if count > 0:
                    print(f"  Saved {count} CSV records to DB")

        except Exception as e:
            print(f"  CSV-to-DB save failed: {e}")

    def _write_fmp_to_csv(self, data: List[Dict[str, Any]]) -> None:
        """FMP DBから取得できた値をCSVに自動書き込み

        DBnomicsの最新月より新しい月のデータをCSVにマージする。
        既存CSV行の空欄フィールドのみFMP値で補完し、既入力値は上書きしない。
        """
        try:
            # DBnomics最新月を特定（source='dbnomics'のみ = 2025-12等）
            from services.usa.ism_components_db_utils import get_latest_date
            db_latest = get_latest_date("manufacturing", source="dbnomics")
            if not db_latest:
                return

            # DBnomics最新月より新しい月のデータを抽出
            new_month_data = {}
            for item in data:
                if item.get("date") and item["date"] > db_latest:
                    date_str = item["date"]  # "YYYY-MM-01"
                    parts = date_str.split("-")
                    csv_date = f"{int(parts[0])}/{int(parts[1])}"  # "2026/1"
                    new_month_data[csv_date] = item

            if not new_month_data:
                return

            CSV_FIELDS = ["new_orders", "production", "employment",
                          "supplier_deliveries", "prices", "inventories"]

            # 既存CSVを読み込み
            existing = {}  # {csv_date: {field: value_str}}
            if CSV_FILE.exists():
                with open(CSV_FILE, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        d = row.get("date", "").strip()
                        if d:
                            existing[d] = {field: row.get(field, "").strip() for field in CSV_FIELDS}

            # マージ: 既存行の空欄フィールドのみFMP値で補完、新しい月は追加
            changed = False
            for csv_date, item in new_month_data.items():
                if csv_date in existing:
                    # 既存行: 空欄フィールドのみ補完
                    for field in CSV_FIELDS:
                        if not existing[csv_date].get(field) and item.get(field) is not None:
                            existing[csv_date][field] = str(item[field])
                            changed = True
                            print(f"  CSV auto-fill: {csv_date} {field}={item[field]}")
                else:
                    # 新しい月: FMP値で行追加
                    row_data = {}
                    has_value = False
                    for field in CSV_FIELDS:
                        val = item.get(field)
                        if val is not None:
                            row_data[field] = str(val)
                            has_value = True
                        else:
                            row_data[field] = ""
                    if has_value:
                        existing[csv_date] = row_data
                        changed = True
                        filled = [f for f in CSV_FIELDS if row_data[f]]
                        print(f"  CSV auto-add: {csv_date} fields={filled}")

            if not changed:
                return

            # CSVを書き直し（日付順）
            CSV_DIR.mkdir(parents=True, exist_ok=True)
            sorted_dates = sorted(existing.keys(),
                                  key=lambda d: (int(d.split("/")[0]), int(d.split("/")[1])))
            with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
                header = "date," + ",".join(CSV_FIELDS)
                f.write(header + "\n")
                for d in sorted_dates:
                    vals = [existing[d].get(field, "") for field in CSV_FIELDS]
                    f.write(d + "," + ",".join(vals) + "\n")

            print(f"  CSV updated: {len(sorted_dates)} rows")

        except Exception as e:
            print(f"  FMP-to-CSV write failed: {e}")

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBからフォールバック読み込み"""
        try:
            from services.usa.ism_components_db_utils import load_ism_components
            db_data = load_ism_components("manufacturing")
            # DB結果にはproduction/business_activityの両方が入るが、製造業ではproductionを使用
            # order_inventory_balance等の派生フィールドは後で再計算される
            return db_data
        except Exception as e:
            print(f"  DB fallback load failed: {e}")
            return []

    def _supplement_from_fmp_db(self, dbnomics_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        DBnomicsデータをFMP DB（economic_calendar_events）の最新データで補完

        FMP DBにはNew Orders, Employment, Pricesが含まれる。
        DBnomicsが遅延している場合、FMP DBからこれらを補完する。
        """
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            # DBnomicsの最新日付を取得
            if not dbnomics_data:
                return dbnomics_data
            latest_date = max(item["date"] for item in dbnomics_data)  # "YYYY-MM-01"
            latest_month = latest_date[:7]  # "YYYY-MM"

            # FMP DBからISM製造業コンポーネントを取得（DBnomics最新以降）
            fmp_components = {
                "new_orders": "ISM Manufacturing New Orders",
                "employment": "ISM Manufacturing Employment",
                "prices": "ISM Manufacturing Prices",
            }

            with SessionLocal() as session:
                new_months = {}
                for field, pattern in fmp_components.items():
                    query = text("""
                        SELECT event, datetime_utc, actual
                        FROM economic_calendar_events
                        WHERE country = 'US'
                          AND event ILIKE :pattern
                          AND actual IS NOT NULL
                          AND datetime_utc > :since
                        ORDER BY datetime_utc ASC
                    """)
                    rows = session.execute(query, {
                        "pattern": f"%{pattern}%",
                        "since": f"{latest_month}-01",
                    }).fetchall()

                    for row in rows:
                        event_name = row[0]
                        actual = float(row[2])
                        # イベント名から月を抽出: "ISM Manufacturing New Orders (Feb)" → Feb
                        import re
                        month_match = re.search(r'\((\w+)\)', event_name)
                        if not month_match:
                            continue
                        month_abbr = month_match.group(1)  # "Jan", "Feb", etc.

                        # 月名→年月変換（発表年を推定）
                        month_map = {
                            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                        }
                        if month_abbr not in month_map:
                            continue
                        mm = month_map[month_abbr]

                        # 年はdatetime_utcから推定
                        event_year = row[1].year
                        # 12月データが1月に発表される場合の補正
                        if mm == '12' and row[1].month <= 2:
                            event_year -= 1
                        data_date = f"{event_year}-{mm}-01"

                        if data_date <= latest_date:
                            continue  # DBnomicsに既にある

                        if data_date not in new_months:
                            new_months[data_date] = {"date": data_date}
                        new_months[data_date][field] = actual

                if not new_months:
                    return dbnomics_data

                # 新しい月のデータをdbnomics_dataに追加
                for date_key, new_data in sorted(new_months.items()):
                    new_orders = new_data.get("new_orders")
                    # inventoriesはFMPにないのでNone
                    entry = {
                        "date": date_key,
                        "new_orders": new_orders,
                        "production": None,
                        "employment": new_data.get("employment"),
                        "supplier_deliveries": None,
                        "prices": new_data.get("prices"),
                        "inventories": None,
                        "order_inventory_balance": None,
                        "order_inventory_balance_3ma": None,
                    }
                    dbnomics_data.append(entry)
                    print(f"  Supplemented from FMP DB: {date_key} (new_orders={new_orders}, employment={new_data.get('employment')}, prices={new_data.get('prices')})")

                # ソート
                dbnomics_data.sort(key=lambda x: x["date"])

                return dbnomics_data

        except Exception as e:
            print(f"Error supplementing from FMP DB: {e}")
            return dbnomics_data

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID)
        }


# シングルトンインスタンス
ism_components_service = ISMComponentsService()
