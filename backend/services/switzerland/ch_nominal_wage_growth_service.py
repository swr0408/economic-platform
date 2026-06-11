"""
スイス名目賃金上昇率サービス
BFS（スイス連邦統計局）から名目賃金上昇率データを取得

指標:
- Nominal Wage Growth（名目賃金上昇率）
- 四半期データ（前年同期比）

データソース:
- BFS（Federal Statistical Office）
- https://dam-api.bfs.admin.ch/hub/api/dam/assets/36210011/master

発表スケジュール:
- FMPマッピングなし
- BFSアジェンダ/RSSから週次チェック

キャッシュ方式: 週次チェック方式
"""
import json
import io
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_nominal_wage_growth_cache.json"


class CHNominalWageGrowthService:
    """スイス名目賃金上昇率サービス"""

    DATA_CACHE_KEY = "switzerland:ch_nominal_wage_growth:data"
    NEXT_RELEASE_CACHE_KEY = "switzerland:ch_nominal_wage_growth:next_release"

    # BFS API URL (CSV format)
    BFS_API_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36210011/master"

    # BFS Agenda/RSS URLs for next release
    BFS_AGENDA_URL = "https://www.bfs.admin.ch/bfs/en/home/news/agenda.html"
    BFS_RSS_URL = "https://www.bfs.admin.ch/bfs/en/home/aktuell/agenda/jcr:content/root/main/agendatopic.rss.agendaTopic.xml?title=&prodima="

    # 検索キーワード（RSSフィード検索用）
    SEARCH_KEYWORDS = ["nominal wage", "wage growth", "wage index", "earnings"]

    # 更新チェック間隔（7日）
    REFRESH_INTERVAL_DAYS = 7

    def __init__(self):
        pass

    def get_nominal_wage_growth_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイス名目賃金上昇率データを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # BFS APIから取得
        bfs_result = self._load_from_bfs()
        if bfs_result:
            # 最新値を取得
            latest = bfs_result[-1] if bfs_result else None

            cache_payload = {
                "data": bfs_result,
                "latest": latest,
                "metadata": {
                    "source": "BFS (Federal Statistical Office)",
                    "indicator": "Nominal Wage Growth",
                    "description": "スイス名目賃金上昇率（前年同期比）",
                    "unit": "%",
                    "frequency": "quarterly",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": bfs_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "bfs_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
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
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_bfs(self) -> List[Dict[str, Any]]:
        """BFS APIからCSVデータを取得してパース"""
        try:
            print(f"[CHNominalWageGrowth] Fetching data from BFS API: {self.BFS_API_URL}")

            from services.switzerland.bfs_asset_resolver import resolve_master_url_from_url
            resp = requests.get(resolve_master_url_from_url(self.BFS_API_URL), timeout=120)
            resp.raise_for_status()

            # CSVをパース
            content = resp.content.decode('utf-8')
            lines = content.strip().split('\n')

            if len(lines) < 2:
                print("[CHNominalWageGrowth] CSV has no data rows")
                return []

            # ヘッダーを解析
            headers = lines[0].split(',')
            print(f"[CHNominalWageGrowth] CSV headers: {headers}")

            # PERIOD, WAGE_TYPE, VALUE_P, STATUS_VALUE_P
            period_idx = headers.index('PERIOD') if 'PERIOD' in headers else 0
            value_idx = headers.index('VALUE_P') if 'VALUE_P' in headers else 2

            result = []
            current_date = datetime.now(JST).date()

            for line in lines[1:]:
                if not line.strip():
                    continue

                # CSVパース（引用符対応）
                parts = self._parse_csv_line(line)
                if len(parts) <= max(period_idx, value_idx):
                    continue

                period = parts[period_idx].strip().strip('"')
                value_str = parts[value_idx].strip().strip('"')

                # YYYY-Q# 形式をパース (例: "2024-Q3")
                match = re.match(r'(\d{4})-Q(\d)', period)
                if not match:
                    continue

                year = int(match.group(1))
                quarter = int(match.group(2))

                # 四半期の末月を計算（Q1=3月, Q2=6月, Q3=9月, Q4=12月）
                month = quarter * 3
                date_formatted = f"{year}-{month:02d}-01"

                # 未来のデータはスキップ
                try:
                    date_obj = datetime.strptime(date_formatted, "%Y-%m-%d").date()
                    if date_obj > current_date:
                        continue
                except ValueError:
                    continue

                # 値をパース
                if not value_str or value_str == '':
                    continue

                try:
                    value_float = float(value_str)
                except (ValueError, TypeError):
                    continue

                result.append({
                    "date": date_formatted,
                    "value": round(value_float, 2),
                    "period": period,  # 元の四半期表記も保持
                })

            # 日付でソートして重複を除去
            result.sort(key=lambda x: x["date"])
            seen_dates = set()
            unique_result = []
            for item in result:
                if item["date"] not in seen_dates:
                    seen_dates.add(item["date"])
                    unique_result.append(item)

            print(f"[CHNominalWageGrowth] Loaded {len(unique_result)} records from BFS API")
            if unique_result:
                print(f"[CHNominalWageGrowth] Date range: {unique_result[0]['date']} to {unique_result[-1]['date']}")
                print(f"[CHNominalWageGrowth] Latest: value={unique_result[-1].get('value')}%")

            return unique_result

        except Exception as e:
            print(f"[CHNominalWageGrowth] Error loading from BFS API: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_csv_line(self, line: str) -> List[str]:
        """CSV行をパース（引用符対応）"""
        result = []
        current = ""
        in_quotes = False

        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                result.append(current)
                current = ""
            else:
                current += char

        result.append(current)
        return result

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得（BFS RSSフィードから検索）"""
        # キャッシュチェック
        cached = redis_client.get(self.NEXT_RELEASE_CACHE_KEY)
        if cached:
            return cached

        try:
            next_release = self._fetch_next_release_from_rss()
            if next_release:
                # 1日キャッシュ
                redis_client.set(self.NEXT_RELEASE_CACHE_KEY, next_release, expire=86400)
                return next_release
        except Exception as e:
            print(f"[CHNominalWageGrowth] Error fetching next release: {e}")

        return None

    def _fetch_next_release_from_rss(self) -> Optional[Dict[str, Any]]:
        """BFS RSSフィードから次回発表日を検索"""
        try:
            import xml.etree.ElementTree as ET

            resp = requests.get(self.BFS_RSS_URL, timeout=30)
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            now = datetime.now(UTC)

            candidates = []

            # RSSアイテムを検索
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                pub_date_elem = item.find('pubDate')

                if title_elem is None or pub_date_elem is None:
                    continue

                title = title_elem.text or ""
                title_lower = title.lower()

                # キーワードマッチ
                matched = False
                for keyword in self.SEARCH_KEYWORDS:
                    if keyword.lower() in title_lower:
                        matched = True
                        break

                if not matched:
                    continue

                # 日付パース (RFC 2822形式)
                pub_date_str = pub_date_elem.text or ""
                try:
                    # "Wed, 25 Feb 2026 12:00:00 +0100" 形式
                    dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
                except ValueError:
                    continue

                # 未来のイベントのみ
                if dt <= now:
                    continue

                dt_jst = dt.astimezone(JST)
                candidates.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "datetime_utc": dt.astimezone(UTC).isoformat(),
                    "datetime_jst": dt_jst.isoformat(),
                    "time_jst": dt_jst.strftime("%H:%M"),
                    "label": title,
                    "_dt": dt,
                })

            if candidates:
                candidates.sort(key=lambda x: x["_dt"])
                result = candidates[0]
                del result["_dt"]
                print(f"[CHNominalWageGrowth] Found next release from RSS: {result['label']} on {result['date']}")
                return result

            print("[CHNominalWageGrowth] No upcoming wage-related events found in RSS")
            return None

        except Exception as e:
            print(f"[CHNominalWageGrowth] Error fetching RSS: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（週次チェック）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            days_since_update = (now - last_updated).days

            # 7日以上経過していれば更新
            return days_since_update >= self.REFRESH_INTERVAL_DAYS

        except Exception as e:
            print(f"[CHNominalWageGrowth] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CHNominalWageGrowth] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHNominalWageGrowth] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.NEXT_RELEASE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "CH Nominal Wage Growth",
            "source": "BFS (Federal Statistical Office)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_nominal_wage_growth_service = CHNominalWageGrowthService()
