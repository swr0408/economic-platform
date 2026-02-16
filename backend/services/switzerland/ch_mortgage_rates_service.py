"""
スイス住宅ローン金利（Interest rates on new loan agreements）サービス
SNB Data Portalから住宅ローン金利データを取得

指標:
- 変動金利住宅ローン（Mortgages with variable interest rates）
  - ベース金利非連動（Not linked to a base rate of interest）
  - 融資額: 50万〜100万CHF, 100万〜500万CHF
  - 中央値（Median）
- 固定金利住宅ローン（Mortgages with fixed interest rates）
  - 融資額: 50万〜100万CHF, 100万〜500万CHF
  - 中央値（Median）

データソース:
- SNB Data Portal: https://data.snb.ch/api/cube/zikredvol/data/csv/en
- Cube: zikredvol (Interest rates on new loan agreements)

発表スケジュール:
- 月次（Monthly banking statistics）
- 20日以降の最初の営業日 09:00（チューリッヒ時間）
- ICSカレンダーから取得

キャッシュ方式: ICSカレンダーベース判定
"""
import json
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.switzerland.snb_calendar_service import get_snb_next_release


JST = ZoneInfo("Asia/Tokyo")
ZURICH = ZoneInfo("Europe/Zurich")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_mortgage_rates_cache.json"


class ChMortgageRatesService:
    """スイス住宅ローン金利サービス"""

    DATA_CACHE_KEY = "switzerland:ch_mortgage_rates:data"

    # SNB Data Portal API URL
    # zikredvol = Interest rates on new loan agreements
    # D0: OBB=Variable (not linked), MBB=Variable (linked), FH=Fixed
    # D1: K5000001MF=500k-1M CHF, K15MF=1M-5M CHF
    # D2: MP1=Median
    DATA_SOURCE_URL = "https://data.snb.ch/api/cube/zikredvol/data/csv/en?dimSel=D0(OBB,FH),D1(K5000001MF,K15MF),D2(MP1)&fromDate=2009-10"

    # 系列コード
    VARIABLE_NOT_LINKED = "OBB"  # Variable, not linked to base rate
    FIXED = "FH"  # Fixed interest rate
    AMOUNT_500K_1M = "K5000001MF"  # 500k-1M CHF
    AMOUNT_1M_5M = "K15MF"  # 1M-5M CHF

    # 次回発表日のカテゴリ（ICSカレンダー）
    CALENDAR_CATEGORY = "monthly_banking_statistics"

    def __init__(self):
        pass

    def get_mortgage_rates_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """住宅ローン金利データを取得"""
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
                    "indicator": "Interest rates on new loan agreements",
                    "description": "スイス住宅ローン金利（新規契約）",
                    "unit": "%",
                    "series": {
                        "variable_500k_1m": "変動金利（50万〜100万CHF）",
                        "variable_1m_5m": "変動金利（100万〜500万CHF）",
                        "fixed_500k_1m": "固定金利（50万〜100万CHF）",
                        "fixed_1m_5m": "固定金利（100万〜500万CHF）",
                    }
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
            print(f"[ChMortgageRates] Fetching data from: {self.DATA_SOURCE_URL}")

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
                        date_str = parts[1].strip('"').strip()
                        try:
                            publishing_date = datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")
                            publishing_date = publishing_date.replace(tzinfo=ZURICH)
                            print(f"[ChMortgageRates] PublishingDate: {publishing_date}")
                        except ValueError as e:
                            print(f"[ChMortgageRates] Error parsing PublishingDate '{date_str}': {e}")
                    break

            # データ部分をDataFrameに読み込み
            df = pd.read_csv(io.StringIO(csv_content), sep=';', skiprows=2)

            print(f"[ChMortgageRates] CSV columns: {df.columns.tolist()}")
            print(f"[ChMortgageRates] Total rows: {len(df)}")

            # 日付ごとにデータをまとめる
            date_values = {}

            for _, row in df.iterrows():
                date_str = row['Date']
                d0_code = row['D0']  # OBB or FH
                d1_code = row['D1']  # K5000001MF or K15MF
                value = row['Value']

                if pd.isna(date_str) or pd.isna(value):
                    continue

                # YYYY-MM形式をYYYY-MM-01に変換
                date_formatted = f"{date_str}-01"

                if date_formatted not in date_values:
                    date_values[date_formatted] = {
                        "date": date_formatted,
                        "variable_500k_1m": None,
                        "variable_1m_5m": None,
                        "fixed_500k_1m": None,
                        "fixed_1m_5m": None,
                    }

                try:
                    val = float(value)
                    # 系列の組み合わせでキーを決定
                    if d0_code == self.VARIABLE_NOT_LINKED:
                        if d1_code == self.AMOUNT_500K_1M:
                            date_values[date_formatted]["variable_500k_1m"] = val
                        elif d1_code == self.AMOUNT_1M_5M:
                            date_values[date_formatted]["variable_1m_5m"] = val
                    elif d0_code == self.FIXED:
                        if d1_code == self.AMOUNT_500K_1M:
                            date_values[date_formatted]["fixed_500k_1m"] = val
                        elif d1_code == self.AMOUNT_1M_5M:
                            date_values[date_formatted]["fixed_1m_5m"] = val
                except (ValueError, TypeError) as e:
                    print(f"[ChMortgageRates] Error parsing value: {e}")
                    continue

            # リストに変換してソート
            result = list(date_values.values())
            result.sort(key=lambda x: x["date"])

            print(f"[ChMortgageRates] Loaded {len(result)} records")
            if result:
                print(f"[ChMortgageRates] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[ChMortgageRates] Latest: variable_500k_1m={latest.get('variable_500k_1m')}, fixed_500k_1m={latest.get('fixed_500k_1m')}")

            return result, publishing_date

        except Exception as e:
            print(f"[ChMortgageRates] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return [], None

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
                        print(f"[ChMortgageRates] Data is stale, release was {next_release_str}")
                        return True
                except ValueError:
                    pass

            # 7日以上経過していたら更新
            if (now - last_updated.astimezone(ZURICH)).days >= 7:
                print("[ChMortgageRates] Cache is older than 7 days, refreshing")
                return True

            return False
        except Exception as e:
            print(f"[ChMortgageRates] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ChMortgageRates] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ChMortgageRates] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        publishing_date_str = cached_data.get("publishing_date") if cached_data else None

        return {
            "indicator": "Swiss Mortgage Rates",
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
ch_mortgage_rates_service = ChMortgageRatesService()
