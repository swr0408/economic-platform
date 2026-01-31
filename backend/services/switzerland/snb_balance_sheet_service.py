"""
SNB中央銀行バランスシート（Central Bank Balance Sheet）サービス
SNB Data Portalからバランスシートデータを取得

指標:
- SNBバランスシート合計（Total Assets / Total Liabilities）

データソース:
- SNB Data Portal: https://data.snb.ch/api/cube/snbbipo/data/csv/en

発表スケジュール:
- 月次（毎月末頃発表、09:00 チューリッヒ時間）
- 次回発表日はSNB統計RSSフィードから過去の発表パターンを分析して推定
- RSS: https://www.snb.ch/public/en/rss/statistics

キャッシュ方式: 発表日ベース判定（PublishingDateの変更を検知）
"""
import json
import io
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ZURICH = ZoneInfo("Europe/Zurich")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "snb_balance_sheet_cache.json"


class SNBBalanceSheetService:
    """SNB中央銀行バランスシートサービス"""

    DATA_CACHE_KEY = "switzerland:snb_balance_sheet:data"
    SCHEDULE_CACHE_KEY = "switzerland:snb_balance_sheet:schedule"

    # SNB Data Portal API URL
    DATA_SOURCE_URL = "https://data.snb.ch/api/cube/snbbipo/data/csv/en"

    # SNB統計RSSフィード（発表履歴を取得）
    RSS_URL = "https://www.snb.ch/public/en/rss/statistics"

    # バランスシート合計の指標コード
    # T0 = Total assets（資産合計 / Bilanzsumme）
    # 注: GFGは金・外貨準備のみで、Total Assetsではない
    TOTAL_ASSETS_CODE = "T0"

    def __init__(self):
        self._publishing_date: Optional[datetime] = None

    def get_balance_sheet_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """SNBバランスシートデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                publishing_date_str = cached_data.get("publishing_date")
                if last_updated_str and not self._should_refresh(last_updated_str, publishing_date_str):
                    # 次回発表日を計算
                    next_release = self._calculate_next_release(publishing_date_str)
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # SNB APIからデータ取得
        result, publishing_date = self._load_from_api()
        if result:
            latest = result[-1] if result else None
            publishing_date_str = publishing_date.strftime("%Y-%m-%d %H:%M") if publishing_date else None
            next_release = self._calculate_next_release(publishing_date_str)

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Swiss National Bank",
                    "indicator": "Central Bank Balance Sheet",
                    "description": "SNB中央銀行バランスシート（総資産）",
                    "unit": "Million CHF",
                },
                "publishing_date": publishing_date_str,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            publishing_date_str = file_cache.get("publishing_date")
            next_release = self._calculate_next_release(publishing_date_str)
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

    def _load_from_api(self) -> tuple[List[Dict[str, Any]], Optional[datetime]]:
        """SNB Data Portal APIからデータを取得

        Returns:
            tuple: (データリスト, PublishingDate)
        """
        try:
            print(f"[SNBBalanceSheet] Fetching data from: {self.DATA_SOURCE_URL}")

            resp = requests.get(self.DATA_SOURCE_URL, timeout=60)
            resp.raise_for_status()

            # CSVをパース（エンコーディング対応）
            csv_content = resp.content.decode('utf-8')
            lines = csv_content.strip().split('\n')

            # メタデータからPublishingDateを取得
            # 形式: "PublishingDate";"2026-01-30 09:00"
            publishing_date = None
            for line in lines[:5]:  # 最初の5行をチェック
                if 'PublishingDate' in line:
                    parts = line.split(';')
                    if len(parts) >= 2:
                        date_str = parts[1].strip('"').strip()
                        try:
                            # "2026-01-30 09:00" 形式
                            publishing_date = datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")
                            publishing_date = publishing_date.replace(tzinfo=ZURICH)
                            print(f"[SNBBalanceSheet] PublishingDate: {publishing_date}")
                        except ValueError as e:
                            print(f"[SNBBalanceSheet] Error parsing PublishingDate '{date_str}': {e}")
                    break

            # データ部分をDataFrameに読み込み
            df = pd.read_csv(io.StringIO(csv_content), sep=';', skiprows=2)

            print(f"[SNBBalanceSheet] CSV columns: {df.columns.tolist()}")
            print(f"[SNBBalanceSheet] Total rows: {len(df)}")

            # バランスシート合計（T0 = Total assets）のみをフィルタ
            df_total = df[df['D0'] == self.TOTAL_ASSETS_CODE].copy()
            print(f"[SNBBalanceSheet] Total assets rows (T0): {len(df_total)}")

            result = []
            for _, row in df_total.iterrows():
                date_str = row['Date']
                value = row['Value']

                # 日付をYYYY-MM-01形式に変換
                if pd.notna(date_str) and pd.notna(value):
                    try:
                        # YYYY-MM形式をYYYY-MM-01に変換
                        date_formatted = f"{date_str}-01"
                        result.append({
                            "date": date_formatted,
                            "value": float(value),
                        })
                    except (ValueError, TypeError) as e:
                        print(f"[SNBBalanceSheet] Error parsing row: {e}")
                        continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[SNBBalanceSheet] Loaded {len(result)} records")
            if result:
                print(f"[SNBBalanceSheet] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[SNBBalanceSheet] Latest: value={result[-1].get('value')}")

            return result, publishing_date

        except Exception as e:
            print(f"[SNBBalanceSheet] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return [], None

    def _get_next_release_from_rss(self) -> Optional[str]:
        """SNB統計RSSフィードから次回発表日を推定

        過去の発表パターンを分析して次回発表日を推定する

        Returns:
            次回発表日（"YYYY-MM-DD"形式、推定値）
        """
        import re

        try:
            # キャッシュをチェック（1日有効）
            cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
            if cached:
                cache_time = cached.get("cached_at")
                if cache_time:
                    cache_dt = datetime.fromisoformat(cache_time)
                    if (datetime.now(JST) - cache_dt).total_seconds() < 86400:  # 24時間
                        return cached.get("next_release")

            print(f"[SNBBalanceSheet] Fetching RSS: {self.RSS_URL}")
            resp = requests.get(self.RSS_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            content = resp.text

            # バランスシート関連のエントリを探す
            items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
            balance_items = []

            for item in items:
                title_match = re.search(r'<title>(.*?)</title>', item)
                if title_match and 'balance sheet' in title_match.group(1).lower():
                    title = title_match.group(1)
                    # タイトルから日付を抽出（例: 2026-01-30 - SNB balance sheet items...）
                    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', title)
                    if date_match:
                        pub_date = datetime.strptime(date_match.group(1), '%Y-%m-%d')
                        balance_items.append(pub_date)

            if not balance_items:
                print("[SNBBalanceSheet] No balance sheet entries found in RSS")
                return None

            # 最新の発表日を取得
            balance_items.sort(reverse=True)
            latest = balance_items[0]
            print(f"[SNBBalanceSheet] Latest release from RSS: {latest.strftime('%Y-%m-%d')}")

            # 過去の発表間隔の平均を計算（約30日）
            if len(balance_items) >= 2:
                intervals = []
                for i in range(min(len(balance_items) - 1, 6)):  # 最大6回分
                    diff = (balance_items[i] - balance_items[i + 1]).days
                    intervals.append(diff)
                avg_interval = sum(intervals) / len(intervals)
            else:
                avg_interval = 30  # デフォルト30日

            # 次回発表日を推定
            next_release = latest + timedelta(days=int(avg_interval))

            # 現在より過去の場合は調整
            now = datetime.now(ZURICH).replace(tzinfo=None)
            while next_release <= now:
                next_release = next_release + timedelta(days=int(avg_interval))

            next_release_str = next_release.strftime("%Y-%m-%d")
            print(f"[SNBBalanceSheet] Next release (estimated): {next_release_str}")

            # キャッシュに保存
            redis_client.set(self.SCHEDULE_CACHE_KEY, {
                "next_release": next_release_str,
                "latest_release": latest.strftime("%Y-%m-%d"),
                "avg_interval_days": avg_interval,
                "cached_at": datetime.now(JST).isoformat()
            }, expire=86400)

            return next_release_str

        except Exception as e:
            print(f"[SNBBalanceSheet] Error fetching RSS: {e}")
            return None

    def _calculate_next_release(self, publishing_date_str: Optional[str]) -> Optional[str]:
        """次回発表日を取得

        1. まずRSSから取得を試みる
        2. RSSが取得できない場合はPublishingDateから推定

        Args:
            publishing_date_str: 最後の発表日時文字列（"YYYY-MM-DD HH:MM"形式）

        Returns:
            次回発表日（"YYYY-MM-DD"形式、推定値）
        """
        # RSSから取得を試みる
        next_release = self._get_next_release_from_rss()
        if next_release:
            return next_release

        # フォールバック: PublishingDateから推定
        try:
            if not publishing_date_str:
                now = datetime.now(ZURICH)
                return self._add_one_month(now).strftime("%Y-%m-%d")

            try:
                pub_date = datetime.strptime(publishing_date_str, "%Y-%m-%d %H:%M")
            except ValueError:
                pub_date = datetime.strptime(publishing_date_str[:10], "%Y-%m-%d")

            next_release = self._add_one_month(pub_date)

            now = datetime.now(ZURICH)
            while next_release.replace(tzinfo=ZURICH) <= now:
                next_release = self._add_one_month(next_release)

            return next_release.strftime("%Y-%m-%d")

        except Exception as e:
            print(f"[SNBBalanceSheet] Error calculating next release: {e}")
            return None

    def _add_one_month(self, dt: datetime) -> datetime:
        """1ヶ月後の日付を計算（月末の調整付き）"""
        import calendar

        year = dt.year
        month = dt.month + 1

        if month > 12:
            month = 1
            year += 1

        _, last_day = calendar.monthrange(year, month)
        day = min(dt.day, last_day)

        return dt.replace(year=year, month=month, day=day)

    def _should_refresh(self, last_updated_str: str, publishing_date_str: Optional[str]) -> bool:
        """キャッシュを更新すべきかどうかを判定

        発表日を過ぎていたら更新する
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # PublishingDateがある場合、次回発表日を計算
            if publishing_date_str:
                next_release_str = self._calculate_next_release(publishing_date_str)
                if next_release_str:
                    next_release = datetime.strptime(next_release_str, "%Y-%m-%d")
                    next_release = next_release.replace(hour=9, minute=0, tzinfo=ZURICH)

                    # 次回発表日を過ぎていて、最後の更新が発表前なら更新
                    if now.astimezone(ZURICH) > next_release and last_updated.astimezone(ZURICH) < next_release:
                        print(f"[SNBBalanceSheet] Data is stale, next release was {next_release_str}")
                        return True

            # 7日以上経過していたら更新
            if (now - last_updated).days >= 7:
                return True

            return False
        except Exception as e:
            print(f"[SNBBalanceSheet] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SNBBalanceSheet] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SNBBalanceSheet] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        publishing_date_str = cached_data.get("publishing_date") if cached_data else None

        return {
            "indicator": "SNB Central Bank Balance Sheet",
            "source": "Swiss National Bank Data Portal",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "publishing_date": publishing_date_str,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(publishing_date_str),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
snb_balance_sheet_service = SNBBalanceSheetService()
