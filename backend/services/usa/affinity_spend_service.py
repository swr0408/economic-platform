"""
Affinity カード支出データサービス
Opportunity Insights Economic TrackerからAffinity支出データを取得

データソース:
- GitHub: OpportunityInsights/EconomicTracker
- CSV: Affinity - National - Monthly.csv

更新スケジュール:
- 不定期（月1〜2回程度）
- GitHubコミット履歴から最新更新日を取得
- 1日1回更新チェック（発表日時が不定のため）

キャッシュ方式: last_updated判定方式
"""
import io
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# GitHub API URL
AFFINITY_CSV_URL = "https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/Affinity%20-%20National%20-%20Monthly.csv"
GITHUB_COMMITS_API = "https://api.github.com/repos/OpportunityInsights/EconomicTracker/commits"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "affinity_spend_cache.json"


class AffinitySpendService:
    """Affinity カード支出サービス"""

    # Redisキャッシュキー
    DATA_CACHE_KEY = "opportunity:affinity:data"

    # データキャッシュ更新間隔（1日）
    DATA_CHECK_INTERVAL = 24 * 60 * 60  # 86400秒

    def __init__(self):
        pass

    def get_affinity_spend_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Affinity支出データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": str, "value": float, "yoy": float, "mom": float}, ...],
                "latest": {...},
                "last_commit": {"date": str, "sha": str} | null,
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
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "last_commit": cached_data.get("last_commit"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache(DATA_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])
                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": data,
                        "latest": file_cache.get("latest"),
                        "last_commit": file_cache.get("last_commit"),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # 外部APIから取得
        api_data = self._fetch_affinity_data()
        last_commit = self._get_last_commit()

        if api_data:
            latest = api_data[-1] if api_data else None
            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_commit": last_commit,
                "last_updated": datetime.now(JST).isoformat()
            }
            # Redisに保存（TTLなし）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(DATA_CACHE_FILE, cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "last_commit": last_commit,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache(DATA_CACHE_FILE)
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "last_commit": file_cache.get("last_commit"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "last_commit": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_affinity_data(self) -> List[Dict[str, Any]]:
        """GitHub CSVからAffinityデータを取得"""
        try:
            print("Fetching Affinity spend data from GitHub...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(AFFINITY_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # CSVをパース
            df = pd.read_csv(io.StringIO(response.text))

            result = []

            for _, row in df.iterrows():
                try:
                    year = int(row.get("year", 0))
                    month = int(row.get("month", 0))

                    if year == 0 or month == 0:
                        continue

                    # 月末日を取得
                    day = int(row.get("day_endofmonth", 1))
                    date_str = f"{year}-{month:02d}-{day:02d}"

                    # spend_s_all を使用（全体支出、季節調整済み）
                    value_raw = row.get("spend_s_all", ".")
                    if value_raw == "." or pd.isna(value_raw):
                        continue

                    value = float(value_raw)

                    result.append({
                        "date": date_str,
                        "value": round(value * 100, 2),  # パーセント表示に変換
                        "yoy": None,  # 後で計算
                        "mom": None   # 後で計算
                    })

                except Exception as e:
                    print(f"Error parsing row: {e}")
                    continue

            # 日付順にソート
            result.sort(key=lambda x: x["date"])

            # 前月比と前年比を計算
            for i, item in enumerate(result):
                # 前月比（1ヶ月前のデータがあれば）
                if i >= 1:
                    prev_value = result[i - 1].get("value")
                    curr_value = item.get("value")
                    if prev_value is not None and curr_value is not None:
                        item["mom"] = round(curr_value - prev_value, 2)

                # 前年比（12ヶ月前のデータがあれば）
                if i >= 12:
                    year_ago_value = result[i - 12].get("value")
                    curr_value = item.get("value")
                    if year_ago_value is not None and curr_value is not None:
                        item["yoy"] = round(curr_value - year_ago_value, 2)

            print(f"Fetched {len(result)} Affinity spend data points")
            return result

        except Exception as e:
            print(f"Error fetching Affinity spend data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - 最終更新から1日以上経過していれば更新
        - GitHubに新しいコミットがあれば更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 1日以上経過していれば更新
            if (now - last_updated).total_seconds() >= self.DATA_CHECK_INTERVAL:
                # GitHubの最新コミットをチェック
                last_commit = self._get_last_commit()
                if last_commit:
                    commit_date_str = last_commit.get("date")
                    if commit_date_str:
                        commit_date = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
                        if commit_date.tzinfo is None:
                            commit_date = commit_date.replace(tzinfo=UTC)
                        commit_date_jst = commit_date.astimezone(JST)

                        # 最終更新後にコミットがあれば更新
                        if commit_date_jst > last_updated:
                            return True

                # コミット取得失敗時も1日1回は更新
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_last_commit(self) -> Optional[Dict[str, Any]]:
        """GitHubから最新コミット情報を取得"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/vnd.github.v3+json"
            }

            params = {
                "path": "data/Affinity - National - Monthly.csv",
                "per_page": 1
            }

            response = requests.get(GITHUB_COMMITS_API, headers=headers, params=params, timeout=15)
            response.raise_for_status()

            commits = response.json()
            if commits and len(commits) > 0:
                commit = commits[0]
                return {
                    "sha": commit.get("sha", "")[:7],
                    "date": commit.get("commit", {}).get("committer", {}).get("date"),
                    "message": commit.get("commit", {}).get("message", "")[:100]
                }

            return None

        except Exception as e:
            print(f"Error fetching GitHub commits: {e}")
            return None

    def _load_file_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, cache_file: Path, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {cache_file}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": data.get("last_updated") if data else None,
            "data_count": len(data.get("data", [])) if data else 0,
            "latest": data.get("latest") if data else None,
            "last_commit": data.get("last_commit") if data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
affinity_spend_service = AffinitySpendService()
