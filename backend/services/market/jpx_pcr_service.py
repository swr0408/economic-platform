"""
JPX 日本株指数オプション Put/Call Ratio サービス

データソース:
  - DB: jpx_put_call_ratio テーブル（SIOP月次 + 日次積み上げ）
  - 日経平均 / TOPIX: yfinance (^N225, TOPIX.T) 日足
  - 日次更新:
    - market_data_whole_day.xlsx → 取引高PCR
    - open_interest.xlsx → 建玉PCR（当日建玉残高）
  - 月次バックフィル: SIOP_D_{yyyymm}.xlsx（前月＋当月）

商品:
  - 日経225オプション (nikkei225)
  - 日経225ミニオプション (nikkei225_mini)
  - TOPIXオプション (topix)

更新スケジュール: 日次 (JST 20:15)

NOTE: JPXは2026年4月13日公表分からシート区分を
  summary_data_Futures / summary_data_OP / market_data_Futures / market_data_OP
  に変更すると案内している。変更後はシート名・列名の調整が必要。
"""
import io
import json
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "jpx_pcr_cache.json"

# Redis
DATA_CACHE_KEY = "market:jpx_pcr:data"

# JPX Daily files
JPX_DAILY_URL = "https://www.jpx.co.jp/markets/derivatives/trading-volume/tvdivq00000014nn-att/{date}_market_data_whole_day.xlsx"
JPX_DAILY_OI_URL = "https://www.jpx.co.jp/markets/derivatives/trading-volume/tvdivq00000014nn-att/{date}open_interest.xlsx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Options sheet cell positions (0-based row/col) for market_data_whole_day.xlsx
# Sheet index 4 (Options), "Total" rows
DAILY_POSITIONS = {
    "nikkei225": {
        "put_vol_row": 14, "put_vol_col": 13,   # N15 (0-based: row14, col13)
        "call_vol_row": 14, "call_vol_col": 17,  # R15 (0-based: row14, col17)
    },
    "nikkei225_mini": {
        "put_vol_row": 26, "put_vol_col": 1,    # B27 (0-based: row26, col1)
        "call_vol_row": 26, "call_vol_col": 5,   # F27 (0-based: row26, col5)
    },
    "topix": {
        "put_vol_row": 38, "put_vol_col": 1,    # B39 (0-based: row38, col1)
        "call_vol_row": 38, "call_vol_col": 5,   # F39 (0-based: row38, col5)
    },
}

# SIOP monthly (for backfilling current month)
SIOP_URL = "https://www.jpx.co.jp/automation/markets/statistics-derivatives/monthly-statistics/files/{yyyy}/SIOP_D_{yyyymm}.xlsx"

PRODUCT_MAP_EN = {
    "Nikkei 225 Options": "nikkei225",
    "Nikkei 225 mini Options": "nikkei225_mini",
    "TOPIX Options": "topix",
}

# open_interest.xlsx summary sheet: col0 product name keywords → DB product key
OI_PRODUCT_KEYWORDS = {
    "日経225\nオプション": "nikkei225",
    "日経225ミニ\nオプション": "nikkei225_mini",
    "TOPIX\nオプション": "topix",
}


class JpxPcrService:
    """JPX 日本株指数オプション Put/Call Ratio サービス"""

    def _should_refresh(self) -> bool:
        """キャッシュの更新が必要かどうか判定
        - 6時間以内に更新済み → スキップ（ただしデータが古すぎる場合は更新）
        """
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
                # データの最終日が3日以上古い場合は更新
                end_date = cached.get("metadata", {}).get("end_date")
                if end_date:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                    if (now.date() - end_dt).days > 3:
                        return True
                return False
            return True
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """PCRデータを取得"""
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
            logger.error(f"[JpxPCR] Build error: {e}")
            import traceback
            traceback.print_exc()

        # フォールバック
        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "JPX Put/Call Ratio"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _get_existing_daily_dates(self) -> set:
        """DBに既に存在する JPX_DAILY ソースの日付を取得"""
        from core.database import SessionLocal
        from sqlalchemy import text

        try:
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT DISTINCT date FROM jpx_put_call_ratio
                    WHERE source = 'JPX_DAILY' OR source = 'SIOP'
                    ORDER BY date DESC
                    LIMIT 60
                """)).fetchall()
                return {row[0].strftime("%Y-%m-%d") for row in rows}
        except Exception:
            return set()

    def _fetch_daily_from_jpx(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """JPX daily market_data_whole_day.xlsx から取引高PCRを取得しDBに保存。
        DB未登録の営業日を直近30日分まで遡って取得する。"""
        import requests
        import pandas as pd
        from core.database import SessionLocal
        from sqlalchemy import text

        now_jst = datetime.now(JST)
        existing_dates = self._get_existing_daily_dates()
        total_inserted = 0

        # 直近30日を試行（欠落日を埋める）
        for days_back in range(30):
            target_date = (now_jst - timedelta(days=days_back)).date()

            # 週末スキップ
            if target_date.weekday() >= 5:
                continue

            date_iso = target_date.strftime("%Y-%m-%d")

            # 既にDBにあればスキップ
            if date_iso in existing_dates:
                continue

            date_str = target_date.strftime("%Y%m%d")
            url = JPX_DAILY_URL.format(date=date_str)

            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                if resp.status_code != 200:
                    continue

                df = pd.read_excel(
                    io.BytesIO(resp.content),
                    sheet_name=4,  # Options sheet
                    header=None,
                )

                inserted_count = 0
                with SessionLocal() as session:
                    for product, pos in DAILY_POSITIONS.items():
                        try:
                            put_vol = df.iloc[pos["put_vol_row"], pos["put_vol_col"]]
                            call_vol = df.iloc[pos["call_vol_row"], pos["call_vol_col"]]

                            if pd.isna(put_vol) or pd.isna(call_vol):
                                continue

                            put_vol_int = int(put_vol)
                            call_vol_int = int(call_vol)
                            volume_pcr = round(put_vol_int / call_vol_int, 4) if call_vol_int > 0 else None

                            session.execute(text("""
                                INSERT INTO jpx_put_call_ratio
                                    (date, product, put_volume, call_volume, volume_pcr, source)
                                VALUES
                                    (:date, :product, :put_volume, :call_volume, :volume_pcr, 'JPX_DAILY')
                                ON CONFLICT (date, product) DO UPDATE SET
                                    put_volume = EXCLUDED.put_volume,
                                    call_volume = EXCLUDED.call_volume,
                                    volume_pcr = EXCLUDED.volume_pcr,
                                    source = CASE
                                        WHEN jpx_put_call_ratio.source = 'SIOP'
                                        THEN jpx_put_call_ratio.source
                                        ELSE 'JPX_DAILY'
                                    END,
                                    updated_at = NOW()
                            """), {
                                "date": date_iso,
                                "product": product,
                                "put_volume": put_vol_int,
                                "call_volume": call_vol_int,
                                "volume_pcr": volume_pcr,
                            })
                            inserted_count += 1
                        except Exception as e:
                            logger.warning(f"[JpxPCR] Daily parse error {product}: {e}")

                    session.commit()

                if inserted_count > 0:
                    total_inserted += inserted_count
                    logger.info(f"[JpxPCR] Daily fetched {date_iso}: {inserted_count} products")

            except Exception as e:
                logger.warning(f"[JpxPCR] Daily fetch failed {date_str}: {e}")
                continue

        if total_inserted > 0:
            logger.info(f"[JpxPCR] Daily total inserted: {total_inserted}")

        return None

    def _fetch_daily_oi_from_jpx(self) -> None:
        """JPX daily open_interest.xlsx から当日の建玉残高を取得しDBに保存。
        ファイルは最新1日分のみ公開されるため、毎日確実に取得する必要がある。"""
        import requests
        import pandas as pd
        from core.database import SessionLocal
        from sqlalchemy import text

        now_jst = datetime.now(JST)

        # 直近5営業日を試行（通常は当日のみ存在）
        for days_back in range(5):
            target_date = (now_jst - timedelta(days=days_back)).date()
            if target_date.weekday() >= 5:
                continue

            date_str = target_date.strftime("%Y%m%d")
            url = JPX_DAILY_OI_URL.format(date=date_str)

            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                if resp.status_code != 200:
                    continue

                df = pd.read_excel(io.BytesIO(resp.content), sheet_name=0, header=None)
                date_iso = target_date.strftime("%Y-%m-%d")

                # col0 でオプション商品名を検索し、プット行(col1="プット")の col3 = put_oi、
                # 次行(col1="コール")の col3 = call_oi を取得
                inserted_count = 0
                with SessionLocal() as session:
                    for row_idx in range(df.shape[0]):
                        cell = df.iloc[row_idx, 0]
                        if pd.isna(cell):
                            continue
                        cell_str = str(cell)

                        product = None
                        for keyword, prod_key in OI_PRODUCT_KEYWORDS.items():
                            if keyword in cell_str:
                                product = prod_key
                                break

                        if product is None:
                            continue

                        # This row should be the put row (col1 = "プット")
                        put_label = df.iloc[row_idx, 1] if pd.notna(df.iloc[row_idx, 1]) else ""
                        if "プット" not in str(put_label):
                            continue

                        # Next row should be call (col1 = "コール")
                        if row_idx + 1 >= df.shape[0]:
                            continue
                        call_label = df.iloc[row_idx + 1, 1] if pd.notna(df.iloc[row_idx + 1, 1]) else ""
                        if "コール" not in str(call_label):
                            continue

                        try:
                            put_oi = df.iloc[row_idx, 3]       # col3 = 当日建玉残高
                            call_oi = df.iloc[row_idx + 1, 3]  # col3 = 当日建玉残高
                            put_vol = df.iloc[row_idx, 2]      # col2 = 取引高
                            call_vol = df.iloc[row_idx + 1, 2] # col2 = 取引高

                            if pd.isna(put_oi) or pd.isna(call_oi):
                                continue

                            put_oi_int = int(put_oi)
                            call_oi_int = int(call_oi)
                            oi_pcr = round(put_oi_int / call_oi_int, 4) if call_oi_int > 0 else None

                            # 取引高も取得（OIファイルにも含まれている）
                            put_vol_int = int(put_vol) if pd.notna(put_vol) else None
                            call_vol_int = int(call_vol) if pd.notna(call_vol) else None
                            volume_pcr = None
                            if put_vol_int is not None and call_vol_int is not None and call_vol_int > 0:
                                volume_pcr = round(put_vol_int / call_vol_int, 4)

                            session.execute(text("""
                                INSERT INTO jpx_put_call_ratio
                                    (date, product, put_volume, call_volume, put_oi, call_oi,
                                     volume_pcr, oi_pcr, source)
                                VALUES
                                    (:date, :product, :put_volume, :call_volume, :put_oi, :call_oi,
                                     :volume_pcr, :oi_pcr, 'JPX_OI_DAILY')
                                ON CONFLICT (date, product) DO UPDATE SET
                                    put_oi = EXCLUDED.put_oi,
                                    call_oi = EXCLUDED.call_oi,
                                    oi_pcr = EXCLUDED.oi_pcr,
                                    put_volume = COALESCE(EXCLUDED.put_volume, jpx_put_call_ratio.put_volume),
                                    call_volume = COALESCE(EXCLUDED.call_volume, jpx_put_call_ratio.call_volume),
                                    volume_pcr = COALESCE(EXCLUDED.volume_pcr, jpx_put_call_ratio.volume_pcr),
                                    source = CASE
                                        WHEN jpx_put_call_ratio.source = 'SIOP'
                                        THEN jpx_put_call_ratio.source
                                        ELSE 'JPX_OI_DAILY'
                                    END,
                                    updated_at = NOW()
                            """), {
                                "date": date_iso,
                                "product": product,
                                "put_volume": put_vol_int,
                                "call_volume": call_vol_int,
                                "put_oi": put_oi_int,
                                "call_oi": call_oi_int,
                                "volume_pcr": volume_pcr,
                                "oi_pcr": oi_pcr,
                            })
                            inserted_count += 1
                            logger.info(f"[JpxPCR] OI daily {product} {date_iso}: put_oi={put_oi_int} call_oi={call_oi_int} oi_pcr={oi_pcr}")
                        except Exception as e:
                            logger.warning(f"[JpxPCR] OI daily parse error {product}: {e}")

                    session.commit()

                if inserted_count > 0:
                    logger.info(f"[JpxPCR] OI daily fetched {date_iso}: {inserted_count} products")
                    return  # OIファイルは1日分のみなので見つかったら終了

            except Exception as e:
                logger.warning(f"[JpxPCR] OI daily fetch failed {date_str}: {e}")
                continue

    def _backfill_siop_month(self, year: int, month: int) -> int:
        """指定月のSIOPファイルからバックフィル（OIデータも取得）。
        挿入レコード数を返す。"""
        import requests
        import pandas as pd
        from core.database import SessionLocal
        from sqlalchemy import text

        yyyymm = f"{year:04d}{month:02d}"
        url = SIOP_URL.format(yyyy=str(year), yyyymm=yyyymm)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            if resp.status_code != 200:
                logger.info(f"[JpxPCR] SIOP {yyyymm} not yet available (HTTP {resp.status_code})")
                return 0

            df = pd.read_excel(io.BytesIO(resp.content), sheet_name="BO_DM0032", header=None)
            rows = df.shape[0]

            records = []
            current_product = None

            for row_idx in range(9, rows):
                product_val = df.iloc[row_idx, 2]  # col C
                if pd.notna(product_val) and isinstance(product_val, str):
                    product_str = product_val.strip()
                    if product_str in PRODUCT_MAP_EN:
                        current_product = PRODUCT_MAP_EN[product_str]
                    elif product_str and product_str not in ("", "Products"):
                        current_product = None

                if current_product is None:
                    continue

                date_val = df.iloc[row_idx, 0]  # col A
                if pd.isna(date_val):
                    continue

                day = None
                date_str_raw = str(date_val).strip()
                if "." in date_str_raw:
                    try:
                        parts = date_str_raw.split(".")
                        m = int(float(parts[0]))
                        d = int(float(parts[1]))
                        if m == month:
                            day = d
                    except (ValueError, IndexError):
                        continue
                else:
                    try:
                        day = int(float(date_str_raw))
                    except (ValueError, TypeError):
                        continue

                if day is None or day < 1 or day > 31:
                    continue

                try:
                    dt = date(year, month, day)
                except ValueError:
                    continue

                put_vol = df.iloc[row_idx, 4]   # E
                call_vol = df.iloc[row_idx, 6]  # G
                put_oi = df.iloc[row_idx, 25]   # Z
                call_oi = df.iloc[row_idx, 27]  # AB

                if pd.isna(put_vol) and pd.isna(call_vol):
                    continue

                def _safe_int(v):
                    if pd.isna(v):
                        return None
                    try:
                        return int(v)
                    except (ValueError, TypeError):
                        return None

                put_vol_int = _safe_int(put_vol) or 0
                call_vol_int = _safe_int(call_vol) or 0
                put_oi_int = _safe_int(put_oi)
                call_oi_int = _safe_int(call_oi)

                volume_pcr = round(put_vol_int / call_vol_int, 4) if call_vol_int > 0 else None
                oi_pcr = None
                if put_oi_int and call_oi_int and call_oi_int > 0:
                    oi_pcr = round(put_oi_int / call_oi_int, 4)

                records.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "product": current_product,
                    "put_volume": put_vol_int,
                    "call_volume": call_vol_int,
                    "put_oi": put_oi_int,
                    "call_oi": call_oi_int,
                    "volume_pcr": volume_pcr,
                    "oi_pcr": oi_pcr,
                })

            if records:
                with SessionLocal() as session:
                    for rec in records:
                        session.execute(text("""
                            INSERT INTO jpx_put_call_ratio
                                (date, product, put_volume, call_volume, put_oi, call_oi,
                                 volume_pcr, oi_pcr, source)
                            VALUES
                                (:date, :product, :put_volume, :call_volume, :put_oi, :call_oi,
                                 :volume_pcr, :oi_pcr, 'SIOP')
                            ON CONFLICT (date, product) DO UPDATE SET
                                put_volume = EXCLUDED.put_volume,
                                call_volume = EXCLUDED.call_volume,
                                put_oi = EXCLUDED.put_oi,
                                call_oi = EXCLUDED.call_oi,
                                volume_pcr = EXCLUDED.volume_pcr,
                                oi_pcr = EXCLUDED.oi_pcr,
                                source = 'SIOP',
                                updated_at = NOW()
                        """), rec)
                    session.commit()

                logger.info(f"[JpxPCR] SIOP backfill {yyyymm}: {len(records)} records")
                return len(records)

        except Exception as e:
            logger.warning(f"[JpxPCR] SIOP backfill error {yyyymm}: {e}")

        return 0

    def _backfill_current_month_siop(self) -> None:
        """当月＋前月のSIOPファイルからバックフィル（OIデータも取得）。
        当月のSIOPが未公開の場合でも前月分で建玉PCRを補完する。"""
        now = datetime.now(JST)
        year = now.year
        month = now.month

        # 前月を計算
        prev_month = month - 1
        prev_year = year
        if prev_month < 1:
            prev_month = 12
            prev_year = year - 1

        # 前月 → 当月の順で取得（前月は確実に公開済み）
        self._backfill_siop_month(prev_year, prev_month)
        self._backfill_siop_month(year, month)

    def _load_from_db(self) -> Dict[str, List[Dict[str, Any]]]:
        """DBから全商品のPCRデータを取得"""
        from core.database import SessionLocal
        from sqlalchemy import text

        try:
            with SessionLocal() as session:
                rows = session.execute(text("""
                    SELECT date, product, put_volume, call_volume, put_oi, call_oi,
                           volume_pcr, oi_pcr
                    FROM jpx_put_call_ratio
                    WHERE volume_pcr IS NOT NULL
                    ORDER BY date ASC
                """)).fetchall()

                result: Dict[str, List[Dict[str, Any]]] = {
                    "nikkei225": [],
                    "nikkei225_mini": [],
                    "topix": [],
                }

                PCR_CAP = 10.0  # Cap extreme PCR values (TOPIX low-volume days)
                for row in rows:
                    product = row[1]
                    if product not in result:
                        continue
                    vol_pcr = float(row[6]) if row[6] is not None else None
                    oi_pcr_val = float(row[7]) if row[7] is not None else None
                    if vol_pcr is not None and vol_pcr > PCR_CAP:
                        vol_pcr = None
                    if oi_pcr_val is not None and oi_pcr_val > PCR_CAP:
                        oi_pcr_val = None
                    result[product].append({
                        "date": row[0].strftime("%Y-%m-%d"),
                        "volume_pcr": vol_pcr,
                        "oi_pcr": oi_pcr_val,
                    })

                for p in result:
                    logger.info(f"[JpxPCR] DB {p}: {len(result[p])} rows")
                return result

        except Exception as e:
            logger.error(f"[JpxPCR] DB load error: {e}")
            return {"nikkei225": [], "nikkei225_mini": [], "topix": []}

    def _get_index_daily(self) -> Dict[str, Dict[str, float]]:
        """yfinanceから日経平均・TOPIX日足終値を取得"""
        import yfinance as yf

        result: Dict[str, Dict[str, float]] = {"nikkei225": {}, "topix": {}}

        # 日経平均
        try:
            ticker = yf.Ticker("^N225")
            end_dt = datetime.now(JST) + timedelta(days=2)
            hist = ticker.history(
                start="2020-01-01",
                end=end_dt.strftime("%Y-%m-%d"),
                interval="1d",
            )
            if not hist.empty:
                for idx, row in hist.iterrows():
                    date_str = idx.strftime("%Y-%m-%d")
                    result["nikkei225"][date_str] = round(float(row["Close"]), 2)
                logger.info(f"[JpxPCR] nikkei225 daily: {len(result['nikkei225'])} days")
        except Exception as e:
            logger.error(f"[JpxPCR] yfinance error ^N225: {e}")

        # TOPIX - ^TPXが取得不可の場合はDB or yfinance_serviceからフォールバック
        topix_tickers = ["^TPX", "1306.T"]
        for ticker_sym in topix_tickers:
            try:
                ticker = yf.Ticker(ticker_sym)
                end_dt = datetime.now(JST) + timedelta(days=2)
                hist = ticker.history(
                    start="2020-01-01",
                    end=end_dt.strftime("%Y-%m-%d"),
                    interval="1d",
                )
                if not hist.empty and len(hist) > 10:
                    for idx, row in hist.iterrows():
                        date_str = idx.strftime("%Y-%m-%d")
                        result["topix"][date_str] = round(float(row["Close"]), 2)
                    logger.info(f"[JpxPCR] topix daily ({ticker_sym}): {len(result['topix'])} days")
                    break
            except Exception as e:
                logger.warning(f"[JpxPCR] yfinance error {ticker_sym}: {e}")

        return result

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """データを構築"""
        logger.info("[JpxPCR] Building data...")

        # 1. JPX daily から最新取引高を取得
        self._fetch_daily_from_jpx()

        # 2. JPX daily open_interest.xlsx から当日の建玉残高を取得
        self._fetch_daily_oi_from_jpx()

        # 3. 前月＋当月SIOPバックフィル（OIデータ含む）
        self._backfill_current_month_siop()

        # 3. DBから全データ取得
        db_data = self._load_from_db()
        if not any(db_data[p] for p in db_data):
            return None

        # 4. 株価指数取得
        index_data = self._get_index_daily()

        # 5. 日付ベースで統合
        all_dates = set()
        for product_data in db_data.values():
            for d in product_data:
                all_dates.add(d["date"])

        # Build lookup dicts
        pcr_lookup: Dict[str, Dict[str, Dict]] = {}
        for product, data_list in db_data.items():
            pcr_lookup[product] = {d["date"]: d for d in data_list}

        result_data: List[Dict[str, Any]] = []
        for dt_str in sorted(all_dates):
            item: Dict[str, Any] = {"date": dt_str}

            # 日経225オプション
            nk = pcr_lookup["nikkei225"].get(dt_str)
            if nk:
                item["nk225_vol_pcr"] = nk["volume_pcr"]
                item["nk225_oi_pcr"] = nk["oi_pcr"]
            else:
                item["nk225_vol_pcr"] = None
                item["nk225_oi_pcr"] = None

            # 日経225ミニ
            nkm = pcr_lookup["nikkei225_mini"].get(dt_str)
            if nkm:
                item["nk225mini_vol_pcr"] = nkm["volume_pcr"]
                item["nk225mini_oi_pcr"] = nkm["oi_pcr"]
            else:
                item["nk225mini_vol_pcr"] = None
                item["nk225mini_oi_pcr"] = None

            # TOPIX
            tp = pcr_lookup["topix"].get(dt_str)
            if tp:
                item["topix_vol_pcr"] = tp["volume_pcr"]
                item["topix_oi_pcr"] = tp["oi_pcr"]
            else:
                item["topix_vol_pcr"] = None
                item["topix_oi_pcr"] = None

            # 株価指数
            item["nikkei225"] = index_data["nikkei225"].get(dt_str)
            item["topix_idx"] = index_data["topix"].get(dt_str)

            result_data.append(item)

        if not result_data:
            return None

        # latestはPCRデータがある最新日
        latest_with_pcr = [d for d in result_data if d.get("nk225_vol_pcr") is not None]
        latest = latest_with_pcr[-1].copy() if latest_with_pcr else result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "JPX / yfinance",
                "data_count": len(result_data),
                "nk225_count": len(db_data["nikkei225"]),
                "nk225mini_count": len(db_data["nikkei225_mini"]),
                "topix_count": len(db_data["topix"]),
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
            logger.error(f"[JpxPCR] Redis save error: {e}")

        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[JpxPCR] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[JpxPCR] Redis load error: {e}")
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
            logger.error(f"[JpxPCR] File load error: {e}")
        return None


# シングルトン
jpx_pcr_service = JpxPcrService()
