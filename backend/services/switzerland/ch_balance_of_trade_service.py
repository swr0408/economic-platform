"""
スイス貿易収支サービス
SNB Data Portal + FMP APIから貿易収支データを取得

指標:
- 貿易収支（Trade Balance / Handelsbilanz）- Total 1（金・貴金属除く）
- 輸出（Exports）
- 輸入（Imports）

データソース:
- SNB Data Portal cube: ausshawarm (Foreign trade by goods category, monthly)
  - D0: E=Imports, A=Exports, H=Trade surplus/deficit
  - D1: GT=Grand Total, CHEM=Chemical/pharma, ME=Machines/electronics, UHR=Watches, etc.
  - D2: WMF=Value in CHF millions
- FMP Economic Calendar: 最新値の先行取得（SNBデータ更新ラグを補完）

注意:
- Total 1（金・貴金属除く）= FMPのBalance of Tradeと一致
- ausshawarm = 品目別外国貿易（Total 1）
- ausshalam = 国別外国貿易（Total 2、金・貴金属含む）← 以前使用

発表スケジュール:
- 月次（翌月18-22日頃）
- FMPイベント: "Balance of Trade"

キャッシュ方式: FMP発表日時ベース + 7日更新
"""
import json
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ZURICH = ZoneInfo("Europe/Zurich")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_balance_of_trade_cache.json"

# 月名→月番号マッピング（FMPイベント名から対象月抽出用）
MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}


class CHBalanceOfTradeService:
    """スイス貿易収支サービス"""

    DATA_CACHE_KEY = "switzerland:ch_balance_of_trade:data"
    ECONALPHA_ID = "ch_balance_of_trade"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERNS = ["Balance of Trade"]

    # SNB Data Portal API URL
    # ausshawarm = Foreign trade by goods category (monthly), Total 1 (excluding gold)
    # D0: E=Imports, A=Exports, H=Trade surplus/deficit
    # D1: GT=Grand Total
    # D2: WMF=Value in CHF millions
    DATA_SOURCE_URL = (
        "https://data.snb.ch/api/cube/ausshawarm/data/csv/en?"
        "dimSel=D0(E,A,H),D1(GT),D2(WMF)"
        "&fromDate=2000-01"
    )

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """貿易収支データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return self._build_response(cached_data, cached=True, source="redis")

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return self._build_response(file_cache, cached=True, source="file")

        # SNB APIからデータを取得
        snb_result = self._fetch_from_snb()

        # FMPから最新値を取得（SNBデータ更新ラグを補完）
        fmp_data = self._fetch_from_fmp()

        if snb_result:
            # FMPデータをSNBデータにマージ
            if fmp_data:
                snb_result = self._merge_fmp_data(snb_result, fmp_data)

            cache_payload = {
                **snb_result,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)
            return self._build_response(cache_payload, cached=False, source="snb_api+fmp")

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return self._build_response(file_cache, cached=True, source="file (fallback)")

        return {
            "data": [],
            "mom_change": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _build_response(self, data: Dict, cached: bool, source: str) -> Dict[str, Any]:
        """レスポンスを構築"""
        next_release = self._get_next_release()
        return {
            "data": data.get("data", []),
            "mom_change": data.get("mom_change", []),
            "latest": data.get("latest"),
            "metadata": data.get("metadata", {}),
            "next_release": next_release,
            "cached": cached,
            "source": source,
            "last_updated": data.get("last_updated"),
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（FMPカレンダー）"""
        try:
            from services.switzerland.fmp_next_release_utils import get_next_release_by_pattern
            for pattern in self.FMP_EVENT_PATTERNS:
                result = get_next_release_by_pattern(pattern, country=self.FMP_COUNTRY)
                if result:
                    return result
        except Exception as e:
            print(f"[CH BalanceOfTrade] Error getting FMP next release: {e}")
        return None

    def _fetch_from_snb(self) -> Optional[Dict[str, Any]]:
        """SNB Data Portal APIからデータを取得（ausshawarm: Total 1）"""
        try:
            print("[CH BalanceOfTrade] Fetching from SNB Data Portal (ausshawarm / Total 1)")
            resp = requests.get(self.DATA_SOURCE_URL, timeout=60)
            resp.raise_for_status()

            csv_content = resp.content.decode("utf-8")
            return self._parse_csv(csv_content)

        except requests.exceptions.RequestException as e:
            print(f"[CH BalanceOfTrade] Request error: {e}")
            return None
        except Exception as e:
            print(f"[CH BalanceOfTrade] Error fetching from SNB: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_csv(self, csv_content: str) -> Optional[Dict[str, Any]]:
        """SNB CSV データをパース（ausshawarm: Total 1、品目別）"""
        try:
            lines = csv_content.strip().split("\n")

            # PublishingDateを取得
            publishing_date = None
            for line in lines[:5]:
                if "PublishingDate" in line:
                    parts = line.split(";")
                    if len(parts) >= 2:
                        date_str = parts[1].strip().strip('"')
                        try:
                            publishing_date = datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")
                            publishing_date = publishing_date.replace(tzinfo=ZURICH)
                            print(f"[CH BalanceOfTrade] PublishingDate: {publishing_date}")
                        except ValueError:
                            pass
                    break

            # 日付ごとに Exports / Imports / Balance を集計
            exports_by_date: Dict[str, float] = {}
            imports_by_date: Dict[str, float] = {}
            balance_by_date: Dict[str, float] = {}

            in_data = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                parts = [p.strip().strip('"') for p in stripped.split(";")]

                if parts[0] == "Date":
                    in_data = True
                    continue

                if in_data and len(parts) >= 5:
                    date_str = parts[0]  # "2025-11"
                    d0 = parts[1]        # E/A/H
                    d1 = parts[2]        # GT
                    d2 = parts[3]        # WMF
                    val_str = parts[4]

                    # Grand Total（GT）かつ CHF millions（WMF）のみ
                    if d1 != "GT" or d2 != "WMF":
                        continue

                    try:
                        val = float(val_str)
                    except ValueError:
                        continue

                    if d0 == "A":
                        exports_by_date[date_str] = val
                    elif d0 == "E":
                        imports_by_date[date_str] = val
                    elif d0 == "H":
                        balance_by_date[date_str] = val

            # 時系列データを構築（十億CHF単位）
            all_dates = sorted(balance_by_date.keys())
            data_list: List[Dict[str, Any]] = []

            for date_str in all_dates:
                bal = round(balance_by_date[date_str] / 1000, 2)  # M -> B
                exp = round(exports_by_date.get(date_str, 0) / 1000, 2)
                imp = round(imports_by_date.get(date_str, 0) / 1000, 2)
                data_list.append({
                    "date": f"{date_str}-01",  # YYYY-MM -> YYYY-MM-01
                    "value": bal,
                    "exports": exp,
                    "imports": imp,
                })

            if not data_list:
                print("[CH BalanceOfTrade] No valid data points")
                return None

            # MoM変化幅（前月との差分）
            mom_change_data: List[Dict[str, Any]] = []
            for i in range(1, len(data_list)):
                current = data_list[i]
                prev = data_list[i - 1]
                change = round(current["value"] - prev["value"], 2)
                mom_change_data.append({
                    "date": current["date"],
                    "value": change,
                })

            latest = data_list[-1] if data_list else None

            metadata = {
                "source": "Swiss National Bank (SNB Data Portal)",
                "indicator": "Balance of Trade",
                "description": "外国貿易収支（Total 1、金・貴金属除く）",
                "unit": "B CHF",
                "cube": "ausshawarm",
                "publishing_date": publishing_date.isoformat() if publishing_date else None,
            }

            print(f"[CH BalanceOfTrade] Processed {len(data_list)} months (SNB), latest: {latest}")

            return {
                "data": data_list,
                "mom_change": mom_change_data,
                "latest": latest,
                "metadata": metadata,
            }

        except Exception as e:
            print(f"[CH BalanceOfTrade] Error parsing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_from_fmp(self) -> List[Dict[str, Any]]:
        """FMPから最新の貿易収支データを取得（SNBデータ更新ラグを補完）"""
        result = []

        try:
            from services.calendar.fmp_service import fmp_service

            today = date.today()
            from_date = today - timedelta(days=90)
            to_date = today + timedelta(days=60)

            events = fmp_service.fetch_calendar(from_date, to_date, country=self.FMP_COUNTRY)

            for event in events:
                if event.get("country") != self.FMP_COUNTRY:
                    continue

                event_name = event.get("event", "")
                matched = False
                for pattern in self.FMP_EVENT_PATTERNS:
                    if pattern.lower() in event_name.lower():
                        matched = True
                        break

                if not matched:
                    continue

                actual = event.get("actual")
                if actual is None:
                    continue

                # 日時パース
                dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
                if not dt_utc:
                    continue

                # イベント名から対象月を抽出 e.g. "Balance of Trade (Dec)"
                match = re.search(r'\((\w{3})\)', event_name)
                if match:
                    month_abbr = match.group(1).lower()
                    if month_abbr in MONTH_MAP:
                        target_month = MONTH_MAP[month_abbr]
                        target_year = dt_utc.year
                        if target_month > dt_utc.month:
                            target_year -= 1
                        date_str = f"{target_year}-{target_month:02d}-01"
                    else:
                        date_str = dt_utc.strftime("%Y-%m-01")
                else:
                    date_str = dt_utc.strftime("%Y-%m-01")

                result.append({
                    "date": date_str,
                    "value": float(actual),
                    "exports": None,
                    "imports": None,
                    "source": "fmp",
                })

                # DBにも保存
                self._save_to_db(event)

            if result:
                print(f"[CH BalanceOfTrade] FMP: {len(result)} data points fetched")

        except Exception as e:
            print(f"[CH BalanceOfTrade] Error fetching from FMP: {e}")

        return result

    def _save_to_db(self, event: dict) -> None:
        """FMPイベントをDBに保存"""
        try:
            from services.calendar.fmp_service import fmp_service
            from core.database import SessionLocal
            from sqlalchemy import text

            processed = fmp_service.process_event(event)

            with SessionLocal() as session:
                query = text("""
                    INSERT INTO economic_calendar_events (
                        provider, event_key, country, currency, event, event_period,
                        datetime_raw, datetime_utc, has_time, impact,
                        previous, estimate, actual, change, change_pct, unit, raw_json
                    ) VALUES (
                        :provider, :event_key, :country, :currency, :event, :event_period,
                        :datetime_raw, :datetime_utc, :has_time, :impact,
                        :previous, :estimate, :actual, :change, :change_pct, :unit, :raw_json
                    )
                    ON CONFLICT (provider, event_key) DO UPDATE SET
                        previous = EXCLUDED.previous,
                        estimate = EXCLUDED.estimate,
                        actual = EXCLUDED.actual,
                        change = EXCLUDED.change,
                        change_pct = EXCLUDED.change_pct,
                        updated_at = NOW()
                """)

                session.execute(query, {
                    "provider": processed["provider"],
                    "event_key": processed["event_key"],
                    "country": processed["country"],
                    "currency": processed["currency"],
                    "event": processed["event"],
                    "event_period": processed["event_period"],
                    "datetime_raw": processed["datetime_raw"],
                    "datetime_utc": processed["datetime_utc"],
                    "has_time": processed["has_time"],
                    "impact": processed["impact"],
                    "previous": processed["previous"],
                    "estimate": processed["estimate"],
                    "actual": processed["actual"],
                    "change": processed["change"],
                    "change_pct": processed["change_pct"],
                    "unit": processed["unit"],
                    "raw_json": json.dumps(processed["raw_json"]),
                })
                session.commit()

        except Exception as e:
            print(f"[CH BalanceOfTrade] Error saving to DB: {e}")

    def _merge_fmp_data(self, snb_result: Dict[str, Any], fmp_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """FMPデータをSNBデータにマージ（SNBにない月のみFMPで補完）"""
        data_list = snb_result.get("data", [])
        snb_dates = {item["date"] for item in data_list}

        added = 0
        for fmp_item in fmp_data:
            if fmp_item["date"] not in snb_dates:
                data_list.append({
                    "date": fmp_item["date"],
                    "value": fmp_item["value"],
                    "exports": None,
                    "imports": None,
                })
                added += 1

        if added > 0:
            # 日付順にソート
            data_list.sort(key=lambda x: x["date"])

            # MoM変化幅を再計算
            mom_change_data: List[Dict[str, Any]] = []
            for i in range(1, len(data_list)):
                current = data_list[i]
                prev = data_list[i - 1]
                change = round(current["value"] - prev["value"], 2)
                mom_change_data.append({
                    "date": current["date"],
                    "value": change,
                })

            snb_result["data"] = data_list
            snb_result["mom_change"] = mom_change_data
            snb_result["latest"] = data_list[-1] if data_list else None

            print(f"[CH BalanceOfTrade] Merged {added} FMP data points, new latest: {snb_result['latest']}")

        return snb_result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            hours_since_update = (now - last_updated).total_seconds() / 3600

            # 7日以上経過していれば更新
            if hours_since_update >= 24 * 7:
                return True

            # FMPパターンベースの更新判定
            try:
                from services.switzerland.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in self.FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country=self.FMP_COUNTRY):
                        print(f"[CH BalanceOfTrade] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[CH BalanceOfTrade] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[CH BalanceOfTrade] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CH BalanceOfTrade] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CH BalanceOfTrade] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "CH Balance of Trade (Total 1)",
            "source": "Swiss National Bank (SNB Data Portal) + FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_balance_of_trade_service = CHBalanceOfTradeService()
