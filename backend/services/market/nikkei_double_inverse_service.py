"""
日経ダブルインバース (1357/13570) 信用残サービス

データソース:
  - CSV: backend/data/csv_import/日経ダブルインバース.csv (週次 2014/7 ~ )
  - 日経平均日足: yfinance (^N225)

更新: 6時間TTL (Redis + ファイル)
"""
import csv
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# パス
CSV_FILE = Path(__file__).parent.parent.parent / "data" / "csv_import" / "日経ダブルインバース.csv"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nikkei_double_inverse_cache.json"

# Redis
DATA_CACHE_KEY = "market:nikkei_double_inverse:data"


def _parse_int(s: str) -> Optional[int]:
    """カンマ付き数値文字列をintに変換。例: '3,519,086' → 3519086"""
    try:
        return int(s.replace(",", "").strip().strip('"'))
    except (ValueError, AttributeError):
        return None


def _parse_float(s: str) -> Optional[float]:
    """カンマ付き数値文字列をfloatに変換"""
    try:
        return float(s.replace(",", "").strip().strip('"'))
    except (ValueError, AttributeError):
        return None


class NikkeiDoubleInverseService:
    """日経ダブルインバース 信用残サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            if (now - last_updated).total_seconds() < 6 * 3600:
                return False
            return True
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """信用残データを取得"""
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[NikkeiDI] Build error: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "CSV + yfinance"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """CSVから信用残データを読み込み、日経平均日足をマージ"""
        import yfinance as yf
        import pandas as pd

        logger.info("[NikkeiDI] Building data from CSV + yfinance...")

        if not CSV_FILE.exists():
            logger.error(f"[NikkeiDI] CSV file not found: {CSV_FILE}")
            return None

        # 1. CSV読み込み
        margin_data: List[Dict[str, Any]] = []
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get("日付", "").strip()
                if not date_str:
                    continue
                try:
                    dt = datetime.strptime(date_str, "%Y/%m/%d")
                except ValueError:
                    try:
                        dt = datetime.strptime(date_str, "%Y/%-m/%-d")
                    except ValueError:
                        # パース失敗時は柔軟にパース
                        parts = date_str.split("/")
                        if len(parts) == 3:
                            dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                        else:
                            continue

                margin_data.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "sell_balance": _parse_int(row.get("売残", "")),
                    "buy_balance": _parse_int(row.get("買残", "")),
                    "sell_change": _parse_int(row.get("売残増減", "")),
                    "buy_change": _parse_int(row.get("買残増減", "")),
                    "margin_ratio": _parse_float(row.get("信用倍率", "")),
                })

        if not margin_data:
            logger.error("[NikkeiDI] No data parsed from CSV")
            return None

        margin_data.sort(key=lambda x: x["date"])

        # 2. 日経平均日足を取得（CSV期間 + 余裕）
        first_date = margin_data[0]["date"]
        try:
            ticker = yf.Ticker("^N225")
            end_dt = datetime.now(JST) + timedelta(days=7)
            hist = ticker.history(
                start=first_date,
                end=end_dt.strftime("%Y-%m-%d"),
                interval="1d",
            )
            if not hist.empty:
                nikkei_df = hist[["Close"]].copy()
                nikkei_df.index = pd.to_datetime(nikkei_df.index).tz_localize(None)
                nikkei_df = nikkei_df.sort_index()
                # forward-fill して営業日以外もカバー
                nikkei_df = nikkei_df.asfreq("D", method="ffill")
            else:
                nikkei_df = pd.DataFrame()
                logger.warning("[NikkeiDI] No Nikkei data from yfinance")
        except Exception as e:
            logger.warning(f"[NikkeiDI] yfinance error (continuing without Nikkei): {e}")
            nikkei_df = pd.DataFrame()

        # 3. マージ
        result_data: List[Dict[str, Any]] = []
        for item in margin_data:
            nikkei_close = None
            if not nikkei_df.empty:
                try:
                    dt = pd.Timestamp(item["date"])
                    if dt in nikkei_df.index:
                        nikkei_close = round(float(nikkei_df.loc[dt, "Close"]), 2)
                    else:
                        # 最も近い過去の営業日を探す
                        mask = nikkei_df.index <= dt
                        if mask.any():
                            nearest = nikkei_df.index[mask][-1]
                            nikkei_close = round(float(nikkei_df.loc[nearest, "Close"]), 2)
                except Exception:
                    pass

            result_data.append({
                "date": item["date"],
                "sell_balance": item["sell_balance"],
                "buy_balance": item["buy_balance"],
                "sell_change": item["sell_change"],
                "buy_change": item["buy_change"],
                "margin_ratio": item["margin_ratio"],
                "nikkei_close": nikkei_close,
            })

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[NikkeiDI] Built {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest: sell={latest.get('sell_balance')}, buy={latest.get('buy_balance')}, "
            f"ratio={latest.get('margin_ratio')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "CSV + yfinance (^N225)",
                "indicator": "Nikkei Double Inverse (1357) Margin Balance",
                "frequency": "weekly",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NikkeiDI] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[NikkeiDI] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NikkeiDI] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[NikkeiDI] File load error: {e}")
        return None


# シングルトン
nikkei_double_inverse_service = NikkeiDoubleInverseService()
