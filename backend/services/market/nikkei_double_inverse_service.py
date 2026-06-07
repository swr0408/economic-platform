"""
日経ダブルインバース (1357/13570) 信用残サービス

データソース:
  - CSV: backend/data/csv_import/日経ダブルインバース.csv (週次 2014/7 ~ 2026/2 ヒストリカルベースライン)
  - kabutan: https://kabutan.jp/stock/kabuka?code=1357&ashi=shin (週次 直近約6ヶ月、ベースライン以降を上書き)
  - 日経平均日足: yfinance (^N225)

JPXは1357(ETF)を「銘柄別信用取引週末残高」に掲載しないためkabutanで補完する。
kabutanの週次表は毎週火曜にJPX確定値が反映される。

更新スケジュール: 日次（market_data_scheduler.JP_CLOSE_SERVICES 経由）
キャッシュ: 6時間TTL (Redis + ファイル)
"""
import csv
import json
import logging
import re
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

# kabutan
KABUTAN_URL = "https://kabutan.jp/stock/kabuka?code=1357&ashi=shin"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


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


def _parse_kabutan_cell(s: str) -> Optional[float]:
    """kabutanセルをパース。'－' / '-' / 空文字 → None。カンマ付き数値 → float。"""
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("，", "")
    if not s or s in ("－", "-", "−", "–"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _fetch_kabutan_weekly_margin() -> List[Dict[str, Any]]:
    """kabutanの週次信用残テーブルから1357のレコードを取得。

    返り値: [{date, sell_balance, buy_balance, margin_ratio}, ...]
    確定値の無い直近行（'－'のみの行）はスキップする。
    """
    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.get(KABUTAN_URL, headers=HTTP_HEADERS, timeout=20)
    except Exception as e:
        logger.warning(f"[NikkeiDI] kabutan fetch error: {e}")
        return []
    if resp.status_code != 200:
        logger.warning(f"[NikkeiDI] kabutan HTTP {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    date_pat = re.compile(r"^\d{2}/\d{2}/\d{2}$")
    target = None
    for t in soup.find_all("table"):
        rows = t.find_all("tr")
        if len(rows) < 2:
            continue
        hdr_cells = rows[0].find_all(["th", "td"])
        hdr_text = "".join(c.get_text(strip=True) for c in hdr_cells)
        if "信用倍率" not in hdr_text:
            continue
        # 2行目以降の最初のセルが YY/MM/DD パターンならこの表
        first_cells = rows[1].find_all(["th", "td"])
        if first_cells and date_pat.match(first_cells[0].get_text(strip=True)):
            target = t
            break

    if target is None:
        logger.warning("[NikkeiDI] kabutan margin table not found")
        return []

    out: List[Dict[str, Any]] = []
    rows = target.find_all("tr")
    for r in rows[1:]:
        cells = [c.get_text(strip=True) for c in r.find_all(["th", "td"])]
        if len(cells) < 8:
            continue
        m = re.match(r"^(\d{2})/(\d{2})/(\d{2})$", cells[0])
        if not m:
            continue
        yy, mm, dd = m.groups()
        date_str = f"20{yy}-{mm}-{dd}"

        sell = _parse_kabutan_cell(cells[5])
        buy = _parse_kabutan_cell(cells[6])
        ratio = _parse_kabutan_cell(cells[7])

        # 残データがすべて None の行 (未確定週) はスキップ
        if sell is None and buy is None and ratio is None:
            continue

        out.append({
            "date": date_str,
            "sell_balance": int(sell) if sell is not None else None,
            "buy_balance": int(buy) if buy is not None else None,
            "margin_ratio": ratio,
        })

    logger.info(f"[NikkeiDI] kabutan: parsed {len(out)} confirmed weekly rows")
    return out


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

        # 1b. kabutan週次信用残を取得しCSVベースラインに上書きマージ
        by_date: Dict[str, Dict[str, Any]] = {r["date"]: r for r in margin_data}
        try:
            kabutan_rows = _fetch_kabutan_weekly_margin()
        except Exception as e:
            logger.warning(f"[NikkeiDI] kabutan fetch failed: {e}")
            kabutan_rows = []

        new_or_updated = 0
        for k in kabutan_rows:
            d = k["date"]
            prev = by_date.get(d)
            if prev is None:
                # 新規日付 → 追記（sell_change/buy_changeは後で計算）
                by_date[d] = {
                    "date": d,
                    "sell_balance": k["sell_balance"],
                    "buy_balance": k["buy_balance"],
                    "sell_change": None,
                    "buy_change": None,
                    "margin_ratio": k["margin_ratio"],
                }
                new_or_updated += 1
            else:
                # 既存日付: 残データのみ kabutan で上書き (None は CSV を尊重)
                for fld in ("sell_balance", "buy_balance", "margin_ratio"):
                    if k.get(fld) is not None:
                        prev[fld] = k[fld]
                # sell_change/buy_change は kabutan が持たないので維持
                new_or_updated += 1

        if new_or_updated:
            logger.info(f"[NikkeiDI] kabutan merge: {new_or_updated} rows touched")

        # 並び替え＋週次差分(sell_change/buy_change)を時系列で再計算
        margin_data = sorted(by_date.values(), key=lambda x: x["date"])
        for i in range(1, len(margin_data)):
            cur = margin_data[i]
            prev = margin_data[i - 1]
            if cur.get("sell_change") is None and cur.get("sell_balance") is not None and prev.get("sell_balance") is not None:
                cur["sell_change"] = cur["sell_balance"] - prev["sell_balance"]
            if cur.get("buy_change") is None and cur.get("buy_balance") is not None and prev.get("buy_balance") is not None:
                cur["buy_change"] = cur["buy_balance"] - prev["buy_balance"]

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
