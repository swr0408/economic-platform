"""
スイス経常収支サービス
SNB Data Portal + FMP APIから経常収支データを取得

指標:
- 経常収支（Current Account）- ネット（受取−支払）

データソース:
- SNB Data Portal cube: bopoverq (Balance of payments overview, quarterly)
  - D0: S0=Current account net, E0=Receipts, A0=Expenses
  - 値は百万CHF単位
- FMP Economic Calendar: 最新値の先行取得（SNBデータ更新ラグを補完）

注意:
- FMPの値はB CHF（十億CHF）単位、SNBはM CHF（百万CHF）→ 十億に変換して統一
- 四半期データ（YYYY-QN形式）

発表スケジュール:
- 四半期（約Q+3ヶ月後）
- FMPイベント: "Current Account (Q2)" 等

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
DATA_CACHE_FILE = CACHE_DIR / "ch_current_account_cache.json"

# 四半期→月マッピング（四半期末月の1日をdate文字列にする）
QUARTER_TO_DATE = {
    "Q1": "-03-01",
    "Q2": "-06-01",
    "Q3": "-09-01",
    "Q4": "-12-01",
}

# FMPイベント名の四半期抽出用
QUARTER_MAP = {
    'q1': 'Q1', 'q2': 'Q2', 'q3': 'Q3', 'q4': 'Q4',
}


class CHCurrentAccountService:
    """スイス経常収支サービス"""

    DATA_CACHE_KEY = "switzerland:ch_current_account:data"
    ECONALPHA_ID = "ch_current_account"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERNS = ["Current Account"]

    # SNB Data Portal API URL
    # bopoverq = Balance of payments overview (quarterly)
    # D0: S0=Current account net
    DATA_SOURCE_URL = (
        "https://data.snb.ch/api/cube/bopoverq/data/csv/en?"
        "dimSel=D0(S0)"
        "&fromDate=2000-Q1"
    )

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """経常収支データを取得"""
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

            from services.usa.fmp_next_release_utils import guarded_last_updated
            _lt = snb_result.get("latest") if isinstance(snb_result, dict) else None
            _new_date = _lt.get("date") if isinstance(_lt, dict) else None
            if not _new_date and isinstance(snb_result, dict) and isinstance(snb_result.get("data"), list) and snb_result["data"]:
                _new_date = snb_result["data"][-1].get("date")
            cache_payload = {
                **snb_result,
                "last_updated": guarded_last_updated(self.DATA_CACHE_KEY, _new_date, datetime.now(JST).isoformat()),
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
            "qoq_change": [],
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
            "qoq_change": data.get("qoq_change", []),
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
            print(f"[CH CurrentAccount] Error getting FMP next release: {e}")
        return None

    def _fetch_from_snb(self) -> Optional[Dict[str, Any]]:
        """SNB Data Portal APIからデータを取得（bopoverq: 国際収支概要）"""
        try:
            print("[CH CurrentAccount] Fetching from SNB Data Portal (bopoverq)")
            resp = requests.get(self.DATA_SOURCE_URL, timeout=60)
            resp.raise_for_status()

            csv_content = resp.content.decode("utf-8")
            return self._parse_csv(csv_content)

        except requests.exceptions.RequestException as e:
            print(f"[CH CurrentAccount] Request error: {e}")
            return None
        except Exception as e:
            print(f"[CH CurrentAccount] Error fetching from SNB: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_csv(self, csv_content: str) -> Optional[Dict[str, Any]]:
        """SNB CSV データをパース（bopoverq: D0=S0 経常収支ネット）"""
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
                            print(f"[CH CurrentAccount] PublishingDate: {publishing_date}")
                        except ValueError:
                            pass
                    break

            # CSVデータをパース
            # bopoverq: 3列 = Date;D0;Value
            data_list: List[Dict[str, Any]] = []

            in_data = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                parts = [p.strip().strip('"') for p in stripped.split(";")]

                if parts[0] == "Date":
                    in_data = True
                    continue

                if in_data and len(parts) >= 3:
                    date_raw = parts[0]   # "2025-Q3"
                    d0 = parts[1]         # "S0"
                    val_str = parts[2]

                    if d0 != "S0":
                        continue

                    try:
                        val_m = float(val_str)  # 百万CHF
                    except ValueError:
                        continue

                    # YYYY-QN → YYYY-MM-01 に変換
                    year_str = date_raw[:4]
                    q_str = date_raw[5:]  # Q1, Q2, Q3, Q4
                    if q_str not in QUARTER_TO_DATE:
                        continue

                    date_formatted = f"{year_str}{QUARTER_TO_DATE[q_str]}"
                    val_b = round(val_m / 1000, 2)  # M → B CHF

                    data_list.append({
                        "date": date_formatted,
                        "value": val_b,
                    })

            if not data_list:
                print("[CH CurrentAccount] No valid data points")
                return None

            # 日付順にソート
            data_list.sort(key=lambda x: x["date"])

            # QoQ変化幅（前四半期との差分）
            qoq_change_data: List[Dict[str, Any]] = []
            for i in range(1, len(data_list)):
                current = data_list[i]
                prev = data_list[i - 1]
                change = round(current["value"] - prev["value"], 2)
                qoq_change_data.append({
                    "date": current["date"],
                    "value": change,
                })

            latest = data_list[-1] if data_list else None

            metadata = {
                "source": "Swiss National Bank (SNB Data Portal)",
                "indicator": "Current Account",
                "description": "経常収支（ネット）",
                "unit": "B CHF",
                "cube": "bopoverq",
                "publishing_date": publishing_date.isoformat() if publishing_date else None,
            }

            print(f"[CH CurrentAccount] Processed {len(data_list)} quarters (SNB), latest: {latest}")

            return {
                "data": data_list,
                "qoq_change": qoq_change_data,
                "latest": latest,
                "metadata": metadata,
            }

        except Exception as e:
            print(f"[CH CurrentAccount] Error parsing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_from_fmp(self) -> List[Dict[str, Any]]:
        """FMPから最新の経常収支データを取得（SNBデータ更新ラグを補完）"""
        result = []

        try:
            from services.calendar.fmp_service import fmp_service

            today = date.today()
            from_date = today - timedelta(days=180)
            to_date = today + timedelta(days=90)

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

                # イベント名から対象四半期を抽出 e.g. "Current Account (Q2)"
                match = re.search(r'\((Q[1-4])\)', event_name)
                if match:
                    q_str = match.group(1)
                    # 四半期を年と合わせてdate文字列に
                    target_year = dt_utc.year
                    # Q3が9月末、Q4が12月末なので発表が翌年になるケースを考慮
                    q_num = int(q_str[1])
                    q_month = q_num * 3
                    if q_month > dt_utc.month:
                        target_year -= 1
                    date_str = f"{target_year}{QUARTER_TO_DATE[q_str]}"
                else:
                    # 四半期が特定できない場合は発表日ベース
                    continue

                result.append({
                    "date": date_str,
                    "value": float(actual),  # FMPはB CHF単位
                    "source": "fmp",
                })

                # DBにも保存
                self._save_to_db(event)

            if result:
                print(f"[CH CurrentAccount] FMP: {len(result)} data points fetched")

        except Exception as e:
            print(f"[CH CurrentAccount] Error fetching from FMP: {e}")

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
            print(f"[CH CurrentAccount] Error saving to DB: {e}")

    def _merge_fmp_data(self, snb_result: Dict[str, Any], fmp_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """FMPデータをSNBデータにマージ（SNBにない四半期のみFMPで補完）"""
        data_list = snb_result.get("data", [])
        snb_dates = {item["date"] for item in data_list}

        added = 0
        for fmp_item in fmp_data:
            if fmp_item["date"] not in snb_dates:
                data_list.append({
                    "date": fmp_item["date"],
                    "value": fmp_item["value"],
                })
                added += 1

        if added > 0:
            data_list.sort(key=lambda x: x["date"])

            # QoQ変化幅を再計算
            qoq_change_data: List[Dict[str, Any]] = []
            for i in range(1, len(data_list)):
                current = data_list[i]
                prev = data_list[i - 1]
                change = round(current["value"] - prev["value"], 2)
                qoq_change_data.append({
                    "date": current["date"],
                    "value": change,
                })

            snb_result["data"] = data_list
            snb_result["qoq_change"] = qoq_change_data
            snb_result["latest"] = data_list[-1] if data_list else None

            print(f"[CH CurrentAccount] Merged {added} FMP data points, new latest: {snb_result['latest']}")

        return snb_result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            hours_since_update = (now - last_updated).total_seconds() / 3600

            if hours_since_update >= 24 * 7:
                return True

            try:
                from services.switzerland.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in self.FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country=self.FMP_COUNTRY):
                        print(f"[CH CurrentAccount] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[CH CurrentAccount] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[CH CurrentAccount] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CH CurrentAccount] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CH CurrentAccount] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "CH Current Account",
            "source": "Swiss National Bank (SNB Data Portal) + FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_current_account_service = CHCurrentAccountService()
