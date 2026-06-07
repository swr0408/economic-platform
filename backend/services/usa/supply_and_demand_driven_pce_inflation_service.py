"""
Supply- and Demand-Driven PCE Inflation サービス
SF Fed から CSV データを取得（PCE需給分解）

指標:
- demand_driven: Demand-driven Inflation（需要起因のインフレ寄与, % pts, YoY）
- ambiguous: Ambiguous（判別不能, % pts, YoY）
- supply_driven: Supply-driven Inflation（供給起因のインフレ寄与, % pts, YoY）
- total: 上記3系列の合計 = コアPCE YoY（参考値）

データソース:
- SF Fed: https://www.frbsf.org/research-and-insights/data-and-indicators/supply-and-demand-driven-pce-inflation/
- CSV URL: https://www.frbsf.org/wp-content/uploads/supply-demand-pce-core-yoy-chart-4.csv

発表スケジュール:
- BEA Personal Income and Outlays（PCE）発表後、SF Fed が数日内に更新
- 次回更新日: PCEと同タイミング（FMP econalpha_id="pce" を使用）

キャッシュ方式:
- PCE発表日時ベースで判定（should_refresh_by_fmp_schedule）
- PCE発表後に SF Fed がまだ更新していない場合、24時間ごとに再取得を試行
- データが更新されたら次回PCE発表までスキップ
"""
import io
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    get_last_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


JST = ZoneInfo("Asia/Tokyo")

SFFED_CSV_URL = "https://www.frbsf.org/wp-content/uploads/supply-demand-pce-core-yoy-chart-4.csv"

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "supply_and_demand_driven_pce_inflation_cache.json"

# 階層型リトライ間隔（PCE発表からの経過時間で切替）
RETRY_PHASE_1_DURATION_HOURS = 6   # PCE発表から0-6h: プロービング期
RETRY_PHASE_2_DURATION_HOURS = 72  # PCE発表から6-72h: 通常リトライ期
RETRY_PHASE_1_INTERVAL_SECONDS = 1 * 60 * 60   # 1時間間隔
RETRY_PHASE_2_INTERVAL_SECONDS = 4 * 60 * 60   # 4時間間隔
RETRY_PHASE_3_INTERVAL_SECONDS = 24 * 60 * 60  # 24時間間隔


class SupplyAndDemandDrivenPceInflationService:
    """SF Fed Supply- and Demand-Driven PCE Inflation サービス"""

    DATA_CACHE_KEY = "inflation:supply_and_demand_driven_pce_inflation:data"
    ECONALPHA_ID = "pce"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Supply- and Demand-Driven PCE Inflation データを取得

        Returns:
            {
                "data": [{
                    "date": "YYYY-MM-DD",
                    "demand_driven": float,
                    "ambiguous": float,
                    "supply_driven": float,
                    "total": float
                }, ...],
                "latest": {...},
                "next_release": {...} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data and not self._should_refresh(cached_data):
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("latest"),
                    "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated"),
                }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache and not self._should_refresh(file_cache):
                redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                return {
                    "data": file_cache.get("data", []),
                    "latest": file_cache.get("latest"),
                    "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                    "cached": True,
                    "source": "file",
                    "last_updated": file_cache.get("last_updated"),
                }

        # SF Fed から取得
        api_data = self._fetch_from_sffed()

        if api_data:
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest.get("date") if latest else None,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": False,
                "source": "api",
                "last_updated": cache_payload["last_updated"],
            }

        # 取得失敗時はキャッシュをフォールバックとして返す
        cached_data = redis_client.get(self.DATA_CACHE_KEY) or self._load_file_cache()
        if cached_data:
            return {
                "data": cached_data.get("data", []),
                "latest": cached_data.get("latest"),
                "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
                "cached": True,
                "source": "fallback",
                "last_updated": cached_data.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _should_refresh(self, cache_payload: Dict[str, Any]) -> bool:
        """
        更新が必要か判定（階層型リトライ）

        ロジック:
        1. last_updatedが無い → 更新
        2. PCE発表時刻を過ぎてキャッシュが古い → 更新
        3. SF Fedデータが直近PCE発表月の前月までカバーしていない場合、
           PCE発表からの経過時間に応じて間隔を切替えてリトライ:
           - 0-6h:  1時間間隔（プロービング期）
           - 6-72h: 4時間間隔（通常リトライ期）
           - 72h+:  24時間間隔（長期遅延期）
        4. データが最新まで追いついていれば、次回PCE発表まで完全スキップ
        """
        last_updated = cache_payload.get("last_updated")
        if not last_updated:
            return True

        # PCE発表ベースの判定（last_updated < last_release ならTrue）
        if should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated):
            return True

        # SF Fedデータがまだ未更新の場合、階層型インターバルでリトライ
        latest_data_date = cache_payload.get("latest_data_date")
        if not latest_data_date:
            return False

        try:
            latest_dt = datetime.strptime(latest_data_date, "%Y-%m-%d")
            latest_month = latest_dt.replace(day=1)

            # 直近のPCE発表情報を取得（PCEは前月分が公表される）
            last_release = get_last_release_from_fmp(self.ECONALPHA_ID)
            if not (last_release and last_release.get("datetime_jst")):
                return False

            release_dt = datetime.strptime(last_release["date"], "%Y-%m-%d")
            expected_month = (release_dt.replace(day=1) - timedelta(days=1)).replace(day=1)

            # データが既に最新まで追いついている → 次回PCE発表まで完全スキップ
            if latest_month >= expected_month:
                return False

            # 経過時間を算出
            now = datetime.now(JST)
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)
            elapsed_since_fetch = (now - last_updated_dt).total_seconds()

            release_datetime_jst = datetime.fromisoformat(last_release["datetime_jst"])
            elapsed_since_pce_hours = (now - release_datetime_jst).total_seconds() / 3600

            # 階層型インターバル判定
            if elapsed_since_pce_hours <= RETRY_PHASE_1_DURATION_HOURS:
                threshold = RETRY_PHASE_1_INTERVAL_SECONDS
                phase = "1h-probing"
            elif elapsed_since_pce_hours <= RETRY_PHASE_2_DURATION_HOURS:
                threshold = RETRY_PHASE_2_INTERVAL_SECONDS
                phase = "4h-normal"
            else:
                threshold = RETRY_PHASE_3_INTERVAL_SECONDS
                phase = "24h-extended"

            if elapsed_since_fetch >= threshold:
                print(
                    f"[supply_demand_pce] Data behind "
                    f"(latest={latest_month:%Y-%m}, expected={expected_month:%Y-%m}), "
                    f"phase={phase}, "
                    f"elapsed_since_pce={elapsed_since_pce_hours:.1f}h, "
                    f"elapsed_since_fetch={elapsed_since_fetch/3600:.1f}h, retry"
                )
                return True

            return False
        except Exception as e:
            print(f"[supply_demand_pce] Error in retry check: {e}")
            return False

    def _fetch_from_sffed(self) -> Optional[List[Dict[str, Any]]]:
        """SF Fed から CSV データを取得"""
        try:
            print("Fetching Supply- and Demand-Driven PCE from SF Fed...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(SFFED_CSV_URL, headers=headers, timeout=60)
            response.raise_for_status()

            text = response.content.decode("utf-8-sig", errors="replace")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if len(lines) < 2:
                print("[supply_demand_pce] CSV too short")
                return None

            # ヘッダー解析（列順を確定）
            header = [h.strip().strip('"').lower() for h in lines[0].split(",")]
            try:
                idx_date = header.index("time_month")
            except ValueError:
                print(f"[supply_demand_pce] Unexpected header: {header}")
                return None

            def _find(*candidates: str) -> Optional[int]:
                for c in candidates:
                    cl = c.lower()
                    for i, h in enumerate(header):
                        if cl in h:
                            return i
                return None

            idx_demand = _find("demand")
            idx_ambig = _find("ambiguous")
            idx_supply = _find("supply")

            if idx_demand is None or idx_ambig is None or idx_supply is None:
                print(
                    f"[supply_demand_pce] Missing required columns. header={header}"
                )
                return None

            result_data: List[Dict[str, Any]] = []
            for line in lines[1:]:
                parts = [p.strip().strip('"') for p in line.split(",")]
                if len(parts) <= max(idx_date, idx_demand, idx_ambig, idx_supply):
                    continue

                date_str = self._parse_time_month(parts[idx_date])
                if not date_str:
                    continue

                try:
                    demand = round(float(parts[idx_demand]), 3)
                    ambig = round(float(parts[idx_ambig]), 3)
                    supply = round(float(parts[idx_supply]), 3)
                except (ValueError, TypeError):
                    continue

                total = round(demand + ambig + supply, 3)
                result_data.append(
                    {
                        "date": date_str,
                        "demand_driven": demand,
                        "ambiguous": ambig,
                        "supply_driven": supply,
                        "total": total,
                    }
                )

            result_data.sort(key=lambda x: x["date"])
            print(f"[supply_demand_pce] Fetched {len(result_data)} records")
            return result_data if result_data else None

        except Exception as e:
            print(f"[supply_demand_pce] Error fetching CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def _parse_time_month(s: str) -> Optional[str]:
        """`2021m3` 形式を `2021-03-01` に変換"""
        m = re.match(r"^\s*(\d{4})m(\d{1,2})\s*$", s)
        if not m:
            return None
        year = int(m.group(1))
        month = int(m.group(2))
        if not (1 <= month <= 12):
            return None
        return f"{year:04d}-{month:02d}-01"

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[supply_demand_pce] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[supply_demand_pce] Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"[supply_demand_pce] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Supply- and Demand-Driven PCE Inflation",
            "source": "SF Fed",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
supply_and_demand_driven_pce_inflation_service = SupplyAndDemandDrivenPceInflationService()
