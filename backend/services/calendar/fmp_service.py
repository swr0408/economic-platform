"""
Financial Modeling Prep (FMP) 経済カレンダーサービス

機能:
- 経済指標発表スケジュールの取得
- DBへの保存（Upsert）
- イベント名の正規化
- EconAlpha指標IDとの紐付け
"""
import hashlib
import json
import re
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

load_dotenv()

# 設定
FMP_API_KEY = os.getenv("FMP_API_KEY", "")
FMP_BASE_URL = "https://financialmodelingprep.com/stable/economic-calendar"
FMP_TIMEOUT = 30

# タイムゾーン
UTC = ZoneInfo("UTC")
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# 対象国コード
# FMP APIは国によってGBではなくUKで返すことがあるため、両方を含める
TARGET_COUNTRIES = {"US", "JP", "EU", "DE", "GB", "UK", "CA", "AU", "CN", "CH", "NZ", "FR", "ES", "IT"}


class FMPService:
    """FMP経済カレンダーAPIサービス"""

    def __init__(self, api_key: str = FMP_API_KEY):
        self.api_key = api_key
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=FMP_TIMEOUT)
        return self._client

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    # =========================================================================
    # API呼び出し
    # =========================================================================

    def fetch_calendar(
        self,
        from_date: date,
        to_date: date,
        country: Optional[str] = None,
        event: Optional[str] = None
    ) -> list:
        """
        指定期間の経済カレンダーを取得

        Args:
            from_date: 開始日
            to_date: 終了日
            country: 国コード（例: "US"）- 指定すると国でフィルタ
            event: イベント名（例: "ISM Manufacturing PMI"）- 指定するとイベント名でフィルタ

        Returns:
            イベントリスト
        """
        if not self.api_key:
            raise ValueError("FMP_API_KEY is not set")

        params = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "apikey": self.api_key,
        }

        # オプションパラメータ
        if country:
            params["country"] = country
        if event:
            params["event"] = event

        filter_info = ""
        if country or event:
            filter_info = f" (country={country}, event={event})"
        print(f"[FMP] Fetching calendar: {from_date} to {to_date}{filter_info}")

        response = self.client.get(FMP_BASE_URL, params=params)
        response.raise_for_status()

        data = response.json()

        if isinstance(data, dict) and "error" in data:
            raise ValueError(f"FMP API Error: {data['error']}")

        print(f"[FMP] Received {len(data)} events")
        return data

    def fetch_calendar_ranges(
        self,
        start_date: date,
        end_date: date,
        range_days: int = 90
    ) -> List[Dict]:
        """
        期間を分割して取得（API制限対策）

        Args:
            start_date: 開始日
            end_date: 終了日
            range_days: 1回のAPI呼び出しで取得する日数

        Returns:
            全イベントリスト
        """
        all_events = []
        current = start_date

        while current <= end_date:
            range_end = min(current + timedelta(days=range_days - 1), end_date)

            try:
                events = self.fetch_calendar(current, range_end)
                all_events.extend(events)
            except Exception as e:
                print(f"[FMP] Error fetching {current} to {range_end}: {e}")

            current = range_end + timedelta(days=1)

        return all_events

    # =========================================================================
    # イベント処理
    # =========================================================================

    @staticmethod
    def generate_event_key(
        provider: str,
        country: Optional[str],
        event: str,
        datetime_raw: str
    ) -> str:
        """イベントの一意キーを生成"""
        raw = f"{provider}|{country or ''}|{event}|{datetime_raw}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def normalize_event_name(event: str) -> str:
        """
        イベント名を正規化

        - 小文字化
        - 余分な空白を削除
        - 括弧内の期間情報を除去
        """
        # 括弧内を除去 (Nov), (Q3), (Dec/19) など
        normalized = re.sub(r'\s*\([^)]*\)\s*$', '', event)
        # 小文字化 & 連続空白を1つに
        normalized = re.sub(r'\s+', ' ', normalized.lower().strip())
        return normalized

    @staticmethod
    def extract_period_info(event: str) -> Optional[str]:
        """
        イベント名から期間情報を抽出

        例:
        - "ISM Manufacturing PMI (Nov)" → "Nov"
        - "GDP Growth Rate QoQ (Q3)" → "Q3"
        - "EIA Crude Oil Stocks Change (Dec/19)" → "Dec/19"
        """
        match = re.search(r'\(([^)]+)\)\s*$', event)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def parse_datetime(datetime_str: str) -> Tuple[Optional[datetime], bool]:
        """
        日時文字列をパース

        Returns:
            (datetime_utc, has_time)
        """
        if not datetime_str:
            return None, False

        # FMPのフォーマット: "2025-12-29 17:00:00"
        try:
            # 時刻が00:00:00の場合は時刻なしとみなす
            dt = datetime.fromisoformat(datetime_str.replace(" ", "T"))
            has_time = not (dt.hour == 0 and dt.minute == 0 and dt.second == 0)

            # UTCとして扱う（FMPはUTCで返す想定）
            dt_utc = dt.replace(tzinfo=UTC)
            return dt_utc, has_time
        except ValueError:
            return None, False

    def process_event(self, raw_event: dict) -> dict:
        """
        生のFMPイベントを処理してDB格納用に変換

        Args:
            raw_event: FMPからのイベント

        Returns:
            処理済みイベント
        """
        country = raw_event.get("country")
        event = raw_event.get("event", "")
        datetime_raw = raw_event.get("date", "")

        datetime_utc, has_time = self.parse_datetime(datetime_raw)

        return {
            "provider": "FMP",
            "event_key": self.generate_event_key("FMP", country, event, datetime_raw),
            "country": country,
            "currency": raw_event.get("currency"),
            "event": event,
            "event_period": self.extract_period_info(event),
            "datetime_raw": datetime_raw,
            "datetime_utc": datetime_utc,
            "has_time": has_time,
            "impact": raw_event.get("impact"),
            "previous": raw_event.get("previous"),
            "estimate": raw_event.get("estimate"),
            "actual": raw_event.get("actual"),
            "change": raw_event.get("change"),
            "change_pct": raw_event.get("changePercentage"),
            "unit": raw_event.get("unit"),
            "raw_json": raw_event,
        }

    def filter_target_countries(self, events: List[Dict]) -> List[Dict]:
        """対象国のイベントのみフィルタ"""
        return [e for e in events if e.get("country") in TARGET_COUNTRIES]


# シングルトンインスタンス
fmp_service = FMPService()
