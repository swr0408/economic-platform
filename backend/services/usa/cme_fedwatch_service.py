"""
CME FedWatch Tool データサービス
CME Groupからデータをスクレイピングして取得
"""
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client, CACHE_TTL_SHORT


class CMEFedWatchService:
    """
    CME FedWatch Tool のデータをスクレイピングで取得
    """

    CACHE_KEY = "usa:fedwatch:probabilities"
    CACHE_TTL = CACHE_TTL_SHORT  # 30分

    # CME FedWatch ページURL
    CME_FEDWATCH_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"

    # APIエンドポイント（JSONデータ取得用）
    CME_API_URL = "https://www.cmegroup.com/services/fedWatch/v1/get-probabilities"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
        })

    def get_probabilities(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        FedWatch確率データを取得

        Returns:
            {
                "data": {
                    "meetings": [...],
                    "rate_levels": [...],
                    "current_rate": str,
                    "last_updated": str
                },
                "cached": bool,
                "source": str
            }
        """
        # 1. Redisキャッシュをチェック
        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY)
            if cached:
                return {
                    "data": cached,
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached.get("last_updated")
                }

        # 2. CMEからデータを取得
        data = self._fetch_from_cme()

        if data:
            # Redisにキャッシュ
            redis_client.set(self.CACHE_KEY, data, expire=self.CACHE_TTL)

            return {
                "data": data,
                "cached": False,
                "source": "cme_api",
                "last_updated": data.get("last_updated")
            }

        # 3. 取得失敗時は古いキャッシュを返す
        cached = redis_client.get(self.CACHE_KEY)
        if cached:
            return {
                "data": cached,
                "cached": True,
                "source": "redis_stale",
                "last_updated": cached.get("last_updated"),
                "error": "Failed to fetch fresh data"
            }

        return {
            "data": None,
            "cached": False,
            "source": "none",
            "error": "No data available"
        }

    def _fetch_from_cme(self) -> Optional[Dict[str, Any]]:
        """
        CME GroupのAPIからFedWatchデータを取得
        """
        try:
            print("Fetching FedWatch data from CME Group...")

            response = self.session.get(self.CME_API_URL, timeout=30)
            response.raise_for_status()

            raw_data = response.json()

            # データを整形
            parsed = self._parse_cme_response(raw_data)

            if parsed:
                parsed["last_updated"] = datetime.now().isoformat()
                parsed["data_source"] = "CME Group FedWatch Tool"
                print(f"Fetched {len(parsed.get('meetings', []))} meetings from CME")
                return parsed

            return None

        except requests.exceptions.RequestException as e:
            print(f"Error fetching from CME API: {e}")
            # フォールバック: Webページをスクレイピング
            return self._scrape_fedwatch_page()
        except Exception as e:
            print(f"Error parsing CME data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_cme_response(self, raw_data: Dict) -> Optional[Dict[str, Any]]:
        """
        CME APIレスポンスをパース
        """
        try:
            meetings = []
            rate_levels = set()

            # CME APIのレスポンス構造に応じてパース
            # 構造: { "meetings": [...], "currentTarget": "..." }

            if "meetings" in raw_data:
                for meeting in raw_data["meetings"]:
                    meeting_date = meeting.get("meetingDate", "")
                    probabilities = {}

                    for prob in meeting.get("probabilities", []):
                        rate_range = prob.get("targetRate", "")
                        probability = prob.get("probability", 0)

                        # "425-450" -> "425-450" (bps形式を維持)
                        if rate_range:
                            rate_levels.add(rate_range)
                            probabilities[rate_range] = round(probability, 2)

                    if meeting_date and probabilities:
                        meetings.append({
                            "date": meeting_date,
                            "probabilities": probabilities
                        })

            # rate_levelsをソート（低い順）
            sorted_rates = sorted(list(rate_levels), key=lambda x: int(x.split("-")[0]) if "-" in x else 0)

            return {
                "meetings": meetings,
                "rate_levels": sorted_rates,
                "current_rate": raw_data.get("currentTarget", ""),
            }

        except Exception as e:
            print(f"Error parsing CME response: {e}")
            return None

    def _scrape_fedwatch_page(self) -> Optional[Dict[str, Any]]:
        """
        CME FedWatchページをスクレイピング（APIがブロックされた場合のフォールバック）
        """
        try:
            print("Falling back to page scraping...")

            response = self.session.get(self.CME_FEDWATCH_URL, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # ページ内のJSONデータを探す
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'fedWatchData' in script.string:
                    # JSONデータを抽出
                    match = re.search(r'fedWatchData\s*=\s*(\{.*?\});', script.string, re.DOTALL)
                    if match:
                        import json
                        data = json.loads(match.group(1))
                        return self._parse_cme_response(data)

            print("Could not find FedWatch data in page, using sample data")
            return self._get_sample_data()

        except Exception as e:
            print(f"Error scraping FedWatch page: {e}, using sample data")
            return self._get_sample_data()

    def _get_sample_data(self) -> Dict[str, Any]:
        """
        サンプルデータを返す（CME APIがブロックされた場合のフォールバック）
        実際の市場データではなく、デモ用のサンプルです
        """
        # 2025年のFOMC会合スケジュール
        meetings = [
            {"date": "2025/01/29", "probabilities": {"400-425": 2.5, "425-450": 97.5}},
            {"date": "2025/03/19", "probabilities": {"375-400": 5.0, "400-425": 35.0, "425-450": 60.0}},
            {"date": "2025/05/07", "probabilities": {"350-375": 3.0, "375-400": 25.0, "400-425": 45.0, "425-450": 27.0}},
            {"date": "2025/06/18", "probabilities": {"350-375": 10.0, "375-400": 40.0, "400-425": 35.0, "425-450": 15.0}},
            {"date": "2025/07/30", "probabilities": {"325-350": 5.0, "350-375": 25.0, "375-400": 45.0, "400-425": 20.0, "425-450": 5.0}},
            {"date": "2025/09/17", "probabilities": {"325-350": 15.0, "350-375": 40.0, "375-400": 35.0, "400-425": 8.0, "425-450": 2.0}},
            {"date": "2025/11/05", "probabilities": {"300-325": 5.0, "325-350": 30.0, "350-375": 45.0, "375-400": 18.0, "400-425": 2.0}},
            {"date": "2025/12/17", "probabilities": {"300-325": 15.0, "325-350": 40.0, "350-375": 35.0, "375-400": 10.0}},
        ]

        rate_levels = ["300-325", "325-350", "350-375", "375-400", "400-425", "425-450"]

        return {
            "meetings": meetings,
            "rate_levels": rate_levels,
            "current_rate": "425-450",
            "last_updated": datetime.now().isoformat(),
            "data_source": "Sample Data (CME API blocked)",
        }

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if exists else -1

        return {
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "ttl_seconds": ttl,
            "ttl_minutes": round(ttl / 60, 1) if ttl > 0 else 0
        }

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)


# シングルトンインスタンス
cme_fedwatch_service = CMEFedWatchService()
