"""
CBO財政見通しサービス
Congressional Budget Office (CBO) のベースライン見通しデータを取得

データソース:
- US-CBO/eval-projections (GitHub)
- https://github.com/US-CBO/eval-projections

更新スケジュール:
- 年2回程度（2月頃、6月頃）
- CBOレポート発表に合わせてGitHubも更新される
"""
import json
import csv
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

import requests

from core.redis_client import redis_client, CACHE_TTL_DAY


class CBOProjectionsService:
    """CBO財政見通しデータサービス"""

    CACHE_KEY = "usa:cbo_projections:data"
    CACHE_TTL = CACHE_TTL_DAY * 30  # 30日間（年2回更新なので長め）
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "fiscal"
    FILE_CACHE_PATH = CACHE_DIR / "cbo_projections_cache.json"

    # GitHub raw URL
    BASELINES_URL = "https://raw.githubusercontent.com/US-CBO/eval-projections/main/input_data/baselines.csv"

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_cbo_projections_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        CBO財政見通しデータを取得

        Returns:
            {
                "data": {
                    "debt": [...],       # 債務見通し
                    "deficit": [...],    # 財政赤字見通し
                    "revenue": [...],    # 歳入見通し（Total）
                    "outlay": [...]      # 歳出見通し（Total）
                },
                "latest_baseline_date": "2025-01-01",
                "projection_years": [2025, 2026, ...],
                "metadata": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # 1. Redis キャッシュをチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                return {
                    "data": cached_data.get("data", {}),
                    "latest_baseline_date": cached_data.get("latest_baseline_date"),
                    "projection_years": cached_data.get("projection_years", []),
                    "metadata": cached_data.get("metadata", {}),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # 2. 外部 API からデータを取得
        api_data = self._fetch_from_github()

        if api_data and api_data.get("data"):
            # Redis にキャッシュ
            cache_payload = {
                "data": api_data["data"],
                "latest_baseline_date": api_data["latest_baseline_date"],
                "projection_years": api_data["projection_years"],
                "metadata": api_data["metadata"],
                "last_updated": datetime.now().isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=self.CACHE_TTL)

            # ファイルキャッシュにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": api_data["data"],
                "latest_baseline_date": api_data["latest_baseline_date"],
                "projection_years": api_data["projection_years"],
                "metadata": api_data["metadata"],
                "cached": False,
                "source": "github",
                "last_updated": datetime.now().isoformat()
            }

        # 3. フォールバック: ファイルキャッシュ
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", {}),
                "latest_baseline_date": file_cache.get("latest_baseline_date"),
                "projection_years": file_cache.get("projection_years", []),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file_cache",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": {},
            "latest_baseline_date": None,
            "projection_years": [],
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_github(self) -> Optional[Dict[str, Any]]:
        """GitHub から CBO baselines.csv を取得・パース"""
        try:
            print("Fetching CBO projections from GitHub...")

            response = requests.get(self.BASELINES_URL, timeout=60)
            response.raise_for_status()

            # CSVをパース
            csv_content = response.text
            reader = csv.DictReader(io.StringIO(csv_content))

            # 最新のbaseline_dateを特定
            all_rows = list(reader)
            if not all_rows:
                print("No CBO data returned from GitHub")
                return None

            # baseline_dateでソートして最新を取得
            baseline_dates = sorted(set(row["baseline_date"] for row in all_rows), reverse=True)
            latest_baseline_date = baseline_dates[0] if baseline_dates else None

            if not latest_baseline_date:
                return None

            print(f"Latest CBO baseline date: {latest_baseline_date}")

            # 最新のbaseline_dateのデータのみ抽出
            latest_rows = [row for row in all_rows if row["baseline_date"] == latest_baseline_date]

            # カテゴリごとにデータを整理
            result_data = {
                "debt": [],
                "deficit": [],
                "revenue": [],
                "outlay": []
            }

            projection_years = set()

            for row in latest_rows:
                component = row["component"]
                category = row["category"]
                fiscal_year = int(row["projected_fiscal_year"])
                value = float(row["value"])

                projection_years.add(fiscal_year)

                # Totalカテゴリのみ抽出（サブカテゴリは除外）
                if category == "Total":
                    if component == "debt":
                        result_data["debt"].append({
                            "fiscal_year": fiscal_year,
                            "value": round(value, 2)
                        })
                    elif component == "deficit":
                        result_data["deficit"].append({
                            "fiscal_year": fiscal_year,
                            "value": round(value, 2)
                        })
                    elif component == "revenue":
                        result_data["revenue"].append({
                            "fiscal_year": fiscal_year,
                            "value": round(value, 2)
                        })
                    elif component == "outlay":
                        result_data["outlay"].append({
                            "fiscal_year": fiscal_year,
                            "value": round(value, 2)
                        })

            # 年度順にソート
            for key in result_data:
                result_data[key].sort(key=lambda x: x["fiscal_year"])

            projection_years_list = sorted(projection_years)

            metadata = {
                "source": "Congressional Budget Office (CBO)",
                "dataset": "Budget Projections Baseline",
                "unit": "billions USD",
                "description": "CBO財政見通し（債務・赤字・歳入・歳出）",
                "github_repo": "US-CBO/eval-projections"
            }

            print(f"Fetched CBO projections for {len(projection_years_list)} years")

            return {
                "data": result_data,
                "latest_baseline_date": latest_baseline_date,
                "projection_years": projection_years_list,
                "metadata": metadata
            }

        except Exception as e:
            print(f"Error fetching CBO projections: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュに保存"""
        try:
            with open(self.FILE_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving file cache: {e}")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュから読み込み"""
        try:
            if self.FILE_CACHE_PATH.exists():
                with open(self.FILE_CACHE_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading file cache: {e}")
        return None

    def invalidate_cache(self) -> bool:
        """Redis キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,
            "ttl_days": round(ttl / 86400, 2) if ttl > 0 else 0,
            "file_cache_exists": self.FILE_CACHE_PATH.exists()
        }


# シングルトンインスタンス
cbo_projections_service = CBOProjectionsService()
