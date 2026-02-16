"""
BOC金融政策報告書（Monetary Policy Report）サービス

指標:
- 実質GDP（前期比・年率換算）
- 実質GDP（前年比）
- CPIインフレ（前年比）
- コアインフレ（前年比）

データソース:
- Bank of Canada Valet API
- https://www.bankofcanada.ca/valet/observations/group/MPR_{YYYY}M{MM}/json

発表スケジュール:
- 年4回（1月、4月、7月、10月）
- 政策金利発表と同時
"""
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boc_mpr_cache.json"


# MPR発表月（1月、4月、7月、10月）
MPR_MONTHS = [1, 4, 7, 10]

# 取得する系列キー
TARGET_SERIES = {
    "gdp_qoq": "SQP_CAN_GDP_QOQ",  # 実質GDP（前期比・年率換算）
    "gdp_yoy": "SQP_CAN_GDP_YOY",  # 実質GDP（前年比）
    "cpi_yoy": "SQP_CAN_CPI_YOY",  # CPIインフレ（前年比）
    "core_yoy": "SQP_CAN_CORE_YOY",  # コアインフレ（前年比）
}

SERIES_LABELS = {
    "gdp_qoq": "実質GDP（前期比年率）",
    "gdp_yoy": "実質GDP（前年比）",
    "cpi_yoy": "CPIインフレ（前年比）",
    "core_yoy": "コアインフレ（前年比）",
}


class BocMprService:
    """BOC金融政策報告書サービス"""

    DATA_CACHE_KEY = "canada:boc_mpr:data"
    CACHE_TTL = 86400 * 7  # 7日間

    def __init__(self):
        pass

    def get_boc_mpr_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """BOC MPRデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "latest_report": cached_data.get("latest_report"),
                        "previous_report": cached_data.get("previous_report"),
                        "comparison": cached_data.get("comparison"),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            cache_payload = {
                "latest_report": result.get("latest_report"),
                "previous_report": result.get("previous_report"),
                "comparison": result.get("comparison"),
                "metadata": {
                    "source": "Bank of Canada",
                    "indicator": "Monetary Policy Report",
                    "description": "BOC金融政策報告書の見通し",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=self.CACHE_TTL)
            self._save_file_cache(cache_payload)

            return {
                "latest_report": result.get("latest_report"),
                "previous_report": result.get("previous_report"),
                "comparison": result.get("comparison"),
                "metadata": cache_payload["metadata"],
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "latest_report": file_cache.get("latest_report"),
                "previous_report": file_cache.get("previous_report"),
                "comparison": file_cache.get("comparison"),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "latest_report": None,
            "previous_report": None,
            "comparison": None,
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _get_recent_mpr_periods(self) -> List[str]:
        """直近のMPR発表期間を取得（最新と前回）"""
        today = date.today()
        periods = []

        # 過去2年分のMPR期間を生成
        for year in range(today.year, today.year - 2, -1):
            for month in reversed(MPR_MONTHS):
                period_date = date(year, month, 1)
                if period_date <= today:
                    periods.append(f"{year}M{month:02d}")
                if len(periods) >= 2:
                    return periods

        return periods

    def _load_from_source(self) -> Optional[Dict[str, Any]]:
        """BOC Valet APIからMPRデータを取得"""
        try:
            periods = self._get_recent_mpr_periods()
            print(f"[BocMpr] Fetching MPR periods: {periods}")

            reports = []
            for period in periods:
                report_data = self._fetch_mpr_report(period)
                if report_data:
                    reports.append(report_data)

            if not reports:
                print("[BocMpr] No MPR data available")
                return None

            latest_report = reports[0] if reports else None
            previous_report = reports[1] if len(reports) > 1 else None

            # 比較データを生成
            comparison = self._generate_comparison(latest_report, previous_report)

            return {
                "latest_report": latest_report,
                "previous_report": previous_report,
                "comparison": comparison,
            }

        except Exception as e:
            print(f"[BocMpr] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_mpr_report(self, period: str) -> Optional[Dict[str, Any]]:
        """特定期間のMPRデータを取得"""
        try:
            url = f"https://www.bankofcanada.ca/valet/observations/group/MPR_{period}/json"
            print(f"[BocMpr] Fetching: {url}")

            resp = requests.get(url, timeout=30)
            if resp.status_code == 404:
                print(f"[BocMpr] MPR {period} not found")
                return None
            resp.raise_for_status()

            data = resp.json()
            observations = data.get("observations", [])

            if not observations:
                return None

            # 期間情報を解析（例: 2025M01 -> 2025年1月）
            year = int(period[:4])
            month = int(period[5:7])
            report_date = f"{year}-{month:02d}-01"

            # 系列データを抽出
            series_data = {}
            for series_key, valet_suffix in TARGET_SERIES.items():
                valet_key = f"MPR_{period}_{valet_suffix}"
                series_data[series_key] = self._extract_series_data(observations, valet_key)

            return {
                "period": period,
                "report_date": report_date,
                "report_label": f"{year}年{month}月",
                "series": series_data,
            }

        except Exception as e:
            print(f"[BocMpr] Error fetching {period}: {e}")
            return None

    def _extract_series_data(self, observations: List[Dict], valet_key: str) -> List[Dict[str, Any]]:
        """特定系列のデータを抽出（四半期データのみ）"""
        result = []

        for obs in observations:
            date_str = obs.get("d", "")
            value_obj = obs.get(valet_key)

            if not value_obj:
                continue

            value_str = value_obj.get("v")
            if not value_str:
                continue

            try:
                value = float(value_str)
                # 四半期の開始日（1月、4月、7月、10月）のみ抽出
                if date_str.endswith(("-01-01", "-04-01", "-07-01", "-10-01")):
                    result.append({
                        "date": date_str,
                        "value": value,
                    })
            except (ValueError, TypeError):
                continue

        # 日付でソート
        result.sort(key=lambda x: x["date"])
        return result

    def _generate_comparison(self, latest: Optional[Dict], previous: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """最新と前回の比較データを生成"""
        if not latest or not previous:
            return None

        comparison = {
            "latest_period": latest.get("report_label"),
            "previous_period": previous.get("report_label"),
            "series_comparison": {},
        }

        for series_key in TARGET_SERIES.keys():
            latest_series = latest.get("series", {}).get(series_key, [])
            previous_series = previous.get("series", {}).get(series_key, [])

            # 共通の日付で比較
            latest_by_date = {item["date"]: item["value"] for item in latest_series}
            previous_by_date = {item["date"]: item["value"] for item in previous_series}

            series_comparison = []
            all_dates = sorted(set(latest_by_date.keys()) | set(previous_by_date.keys()))

            for date_str in all_dates:
                latest_val = latest_by_date.get(date_str)
                previous_val = previous_by_date.get(date_str)
                diff = None
                if latest_val is not None and previous_val is not None:
                    diff = round(latest_val - previous_val, 2)

                series_comparison.append({
                    "date": date_str,
                    "latest": latest_val,
                    "previous": previous_val,
                    "diff": diff,
                })

            comparison["series_comparison"][series_key] = {
                "label": SERIES_LABELS.get(series_key, series_key),
                "data": series_comparison,
            }

        return comparison

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            today = now.date()

            # MPR発表月かつ発表日（通常は月の後半）を過ぎたらリフレッシュ
            if today.month in MPR_MONTHS and today.day >= 20:
                # 最終更新がこの月の20日以前ならリフレッシュ
                if last_updated.date() < date(today.year, today.month, 20):
                    return True

            # 7日以上経過していたらリフレッシュ
            age = now - last_updated
            if age.days >= 7:
                return True

            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[BocMpr] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BocMpr] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BOC Monetary Policy Report",
            "source": "Bank of Canada",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "latest_period": cached_data.get("latest_report", {}).get("period") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
boc_mpr_service = BocMprService()
