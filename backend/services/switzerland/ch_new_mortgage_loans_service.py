"""
スイス新規住宅ローン金額サービス（New Mortgage Loans Volume）
SNB Data Portalから新規住宅ローン融資額データを取得

データソース:
- SNB Data Portal: https://data.snb.ch/en/topics/banken/cube/bahypoakredq
- Cube: bahypoakredq (Quarterly banking statistics - mortgage loans)
- Parameters: d0(LIM)=限度額, d1(T)=合計, d2(VOL)=金額

発表スケジュール:
- 四半期（Quarterly banking statistics）
- ICSカレンダーから取得

キャッシュ方式: ICSカレンダーベース判定
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd
import io

from core.redis_client import redis_client
from services.switzerland.snb_calendar_service import get_snb_next_release


JST = ZoneInfo("Asia/Tokyo")
ZURICH = ZoneInfo("Europe/Zurich")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_new_mortgage_loans_cache.json"


class ChNewMortgageLoansService:
    """スイス新規住宅ローン金額サービス"""

    DATA_CACHE_KEY = "switzerland:ch_new_mortgage_loans:data"

    # SNB Data Portal API URL
    # bahypoakredq = Quarterly banking statistics - mortgage loans
    # d0(LIM): 限度額区分
    # d1(T): 合計
    # d2(VOL): 金額（Volume）
    DATA_SOURCE_URL = "https://data.snb.ch/api/cube/bahypoakredq/data/csv/en?dimSel=d0(LIM),d1(T),d2(VOL)&fromDate=2018-Q1"

    # 次回発表日のカテゴリ（ICSカレンダー）
    CALENDAR_CATEGORY = "quarterly_banking_statistics"

    def __init__(self):
        pass

    def get_new_mortgage_loans_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """新規住宅ローン金額データを取得"""
        # 次回発表日を取得（ICSカレンダーから）
        next_release = get_snb_next_release(self.CALENDAR_CATEGORY)

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                publishing_date_str = cached_data.get("publishing_date")
                if last_updated_str and not self._should_refresh(last_updated_str, next_release):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "last_publishing_date": publishing_date_str,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # SNB APIからデータ取得
        result, publishing_date = self._load_from_api()
        if result:
            latest = result[-1] if result else None
            publishing_date_str = publishing_date.strftime("%Y-%m-%d %H:%M") if publishing_date else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Swiss National Bank",
                    "indicator": "New Mortgage Loans Volume",
                    "description": "新規住宅ローン融資額",
                    "unit": "billion CHF",
                    "frequency": "quarterly",
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
                "last_publishing_date": publishing_date_str,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            publishing_date_str = file_cache.get("publishing_date")
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "last_publishing_date": publishing_date_str,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "last_publishing_date": None,
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
            print(f"[ChNewMortgageLoans] Fetching data from: {self.DATA_SOURCE_URL}")

            resp = requests.get(self.DATA_SOURCE_URL, timeout=60)
            resp.raise_for_status()

            # CSVをパース
            csv_content = resp.content.decode('utf-8')
            lines = csv_content.strip().split('\n')

            # メタデータからPublishingDateを取得
            publishing_date = None
            for line in lines[:5]:
                if 'PublishingDate' in line:
                    parts = line.split(';')
                    if len(parts) >= 2:
                        date_str = parts[1].strip().strip('"')
                        try:
                            publishing_date = datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")
                            publishing_date = publishing_date.replace(tzinfo=ZURICH)
                            print(f"[ChNewMortgageLoans] PublishingDate: {publishing_date}")
                        except ValueError as e:
                            print(f"[ChNewMortgageLoans] Error parsing PublishingDate '{date_str}': {e}")
                    break

            # データ部分をDataFrameに読み込み
            df = pd.read_csv(io.StringIO(csv_content), sep=';', skiprows=2)

            print(f"[ChNewMortgageLoans] CSV columns: {df.columns.tolist()}")
            print(f"[ChNewMortgageLoans] Total rows: {len(df)}")

            result = []

            for _, row in df.iterrows():
                date_str = row['Date']
                value = row['Value']

                if pd.isna(date_str) or pd.isna(value):
                    continue

                # 四半期を日付に変換 (YYYY-QN → YYYY-MM-01)
                # Q1→01, Q2→04, Q3→07, Q4→10
                try:
                    year, quarter = date_str.split('-')
                    quarter_num = int(quarter[1])
                    month = (quarter_num - 1) * 3 + 1
                    date_formatted = f"{year}-{month:02d}-01"

                    # 値を10億CHF単位に変換（元データは千CHF？実際は数百万〜数千万の値）
                    # 値を確認: 15478943.78 → 約1550万 → 10億CHF単位なら約15.5
                    val = float(value) / 1_000_000  # 百万CHF単位に変換

                    result.append({
                        "date": date_formatted,
                        "quarter": date_str,
                        "value": round(val, 2),
                    })
                except (ValueError, IndexError) as e:
                    print(f"[ChNewMortgageLoans] Error parsing row: {e}")
                    continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            # QoQ（前期比）とYoY（前年比）を計算
            result = self._calculate_changes(result)

            print(f"[ChNewMortgageLoans] Loaded {len(result)} records")
            if result:
                print(f"[ChNewMortgageLoans] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[ChNewMortgageLoans] Latest value: {result[-1].get('value')} million CHF")

            return result, publishing_date

        except Exception as e:
            print(f"[ChNewMortgageLoans] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return [], None

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """QoQ（前期比）とYoY（前年比）を計算

        Args:
            data: 日付昇順にソートされたデータリスト

        Returns:
            QoQ/YoY計算済みのデータリスト
        """
        if not data:
            return data

        # 四半期→インデックスのマッピングを作成
        quarter_map = {item["quarter"]: i for i, item in enumerate(data)}

        for i, item in enumerate(data):
            quarter = item["quarter"]  # 例: "2024-Q1"
            value = item["value"]

            # QoQ（前期比）: 1四半期前と比較
            qoq = None
            if i > 0:
                prev_value = data[i - 1]["value"]
                if prev_value and prev_value != 0:
                    qoq = round((value - prev_value) / prev_value * 100, 2)

            # YoY（前年比）: 4四半期前と比較
            yoy = None
            try:
                year, q = quarter.split('-')
                prev_year_quarter = f"{int(year) - 1}-{q}"
                if prev_year_quarter in quarter_map:
                    prev_year_idx = quarter_map[prev_year_quarter]
                    prev_year_value = data[prev_year_idx]["value"]
                    if prev_year_value and prev_year_value != 0:
                        yoy = round((value - prev_year_value) / prev_year_value * 100, 2)
            except (ValueError, KeyError):
                pass

            item["qoq"] = qoq
            item["yoy"] = yoy

        return data

    def _should_refresh(self, last_updated_str: str, next_release_str: Optional[str]) -> bool:
        """キャッシュを更新すべきかどうかを判定

        次回発表日を過ぎていて、最後の更新がその前なら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(ZURICH)

            if next_release_str:
                # 次回発表日時をパース
                try:
                    next_release = datetime.strptime(next_release_str, "%Y-%m-%d %H:%M")
                    next_release = next_release.replace(tzinfo=ZURICH)

                    # 発表日を過ぎていて、最後の更新がその前なら更新
                    if now > next_release and last_updated.astimezone(ZURICH) < next_release:
                        print(f"[ChNewMortgageLoans] Data is stale, release was {next_release_str}")
                        return True
                except ValueError:
                    pass

            # 7日以上経過していたら更新
            if (now - last_updated.astimezone(ZURICH)).days >= 7:
                print("[ChNewMortgageLoans] Cache is older than 7 days, refreshing")
                return True

            return False
        except Exception as e:
            print(f"[ChNewMortgageLoans] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ChNewMortgageLoans] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ChNewMortgageLoans] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        publishing_date_str = cached_data.get("publishing_date") if cached_data else None

        return {
            "indicator": "Swiss New Mortgage Loans",
            "source": "Swiss National Bank Data Portal",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "publishing_date": publishing_date_str,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_snb_next_release(self.CALENDAR_CATEGORY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_new_mortgage_loans_service = ChNewMortgageLoansService()
