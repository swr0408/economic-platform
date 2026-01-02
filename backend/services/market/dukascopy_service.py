"""
Dukascopy を使用した分足データ取得サービス

機能:
- 1分足・5分足のOHLCデータ取得
- 指標発表時刻前後のデータ取得（±1時間、±24時間）
- TimescaleDB への保存
- バックグラウンド差分更新（TTL 15日）
- 対象銘柄: 主要FX、ゴールド、原油、株価指数

使用ライブラリ: dukascopy-python
インストール: pip install dukascopy-python
"""
import logging
import threading
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from services.market.market_repository import market_repository
from services.market.dukascopy_symbols import (
    DUKASCOPY_SYMBOLS,
    get_dukascopy_symbol_by_id,
    get_dukascopy_const_name,
)

# ロガー設定
logger = logging.getLogger(__name__)

# タイムゾーン
UTC = ZoneInfo("UTC")
JST = ZoneInfo("Asia/Tokyo")


# Dukascopy銘柄マッピング
# 内部symbol_id → dukascopy_python.instruments の定数名
def _get_dukascopy_instruments():
    """dukascopy_pythonのinstrument定数をロード"""
    try:
        from dukascopy_python import instruments
        return {
            # 主要FX (ドルストレート)
            "usdjpy": instruments.INSTRUMENT_FX_MAJORS_USD_JPY,
            "eurusd": instruments.INSTRUMENT_FX_MAJORS_EUR_USD,
            "gbpusd": instruments.INSTRUMENT_FX_MAJORS_GBP_USD,
            "audusd": instruments.INSTRUMENT_FX_MAJORS_AUD_USD,
            "nzdusd": instruments.INSTRUMENT_FX_MAJORS_NZD_USD,
            "usdcad": instruments.INSTRUMENT_FX_MAJORS_USD_CAD,
            "usdchf": instruments.INSTRUMENT_FX_MAJORS_USD_CHF,
            # クロス円
            "eurjpy": instruments.INSTRUMENT_FX_CROSSES_EUR_JPY,
            "gbpjpy": instruments.INSTRUMENT_FX_CROSSES_GBP_JPY,
            "audjpy": instruments.INSTRUMENT_FX_CROSSES_AUD_JPY,
            # ゴールド・シルバー
            "gold": instruments.INSTRUMENT_FX_METALS_XAU_USD,
            "silver": instruments.INSTRUMENT_FX_METALS_XAG_USD,
            # 原油
            "crude_oil": instruments.INSTRUMENT_CMD_ENERGY_E_LIGHT,  # WTI
            "brent_oil": instruments.INSTRUMENT_CMD_ENERGY_E_BRENT,  # Brent
            # 株価指数 (CFD)
            "sp500": instruments.INSTRUMENT_IDX_AMERICA_E_SANDP_500,
            "dow": instruments.INSTRUMENT_IDX_AMERICA_E_D_J_IND,
            "nasdaq100": instruments.INSTRUMENT_IDX_AMERICA_E_NQ_100,
            "nikkei225": instruments.INSTRUMENT_IDX_ASIA_E_N225JAP,
            "dax": instruments.INSTRUMENT_IDX_EUROPE_E_DAAX,
        }
    except ImportError:
        return {}

# 遅延ロード用のキャッシュ
_DUKASCOPY_INSTRUMENTS_CACHE = None

def get_dukascopy_instruments():
    global _DUKASCOPY_INSTRUMENTS_CACHE
    if _DUKASCOPY_INSTRUMENTS_CACHE is None:
        _DUKASCOPY_INSTRUMENTS_CACHE = _get_dukascopy_instruments()
    return _DUKASCOPY_INSTRUMENTS_CACHE

# 注意: DUKASCOPY_SYMBOLS は dukascopy_symbols モジュールからインポートされています
# （旧定義は削除済み - リスト型が正しい形式）


class DukascopyService:
    """Dukascopyを使用した分足データ取得サービス"""

    # TTL設定（日数）
    SYNC_TTL_DAYS = 15
    # 1年分のデータを保持
    DATA_RETENTION_DAYS = 365

    def __init__(self):
        self._dukascopy_available = None
        self._background_tasks: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def _check_dukascopy_available(self) -> bool:
        """dukascopy-pythonライブラリが利用可能かチェック"""
        if self._dukascopy_available is not None:
            return self._dukascopy_available

        try:
            import dukascopy_python
            self._dukascopy_available = True
            logger.info("dukascopy-python is available")
        except ImportError:
            self._dukascopy_available = False
            logger.warning("dukascopy-python is not installed. Run: pip install dukascopy-python")

        return self._dukascopy_available

    def get_dukascopy_instrument(self, symbol_id: str):
        """内部symbol_idからDukascopyのinstrumentオブジェクトを取得"""
        # まず新しい銘柄マスタから定数名を取得
        symbol_info = get_dukascopy_symbol_by_id(symbol_id)
        if symbol_info and symbol_info.get("dukascopy_const"):
            const_name = symbol_info["dukascopy_const"]
            try:
                from dukascopy_python import instruments
                return getattr(instruments, const_name, None)
            except ImportError:
                pass

        # 旧方式（後方互換性）
        instruments = get_dukascopy_instruments()
        return instruments.get(symbol_id)

    def get_supported_symbols(self) -> List[str]:
        """サポートされている銘柄IDのリストを取得"""
        return [s["id"] for s in DUKASCOPY_SYMBOLS]

    def fetch_intraday_data(
        self,
        symbol_id: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = "1m",
        offer_side: str = "bid"
    ) -> List[Dict[str, Any]]:
        """
        Dukascopyから分足データを取得

        Args:
            symbol_id: 銘柄ID (例: "usdjpy", "gold")
            start_time: 開始日時 (UTC)
            end_time: 終了日時 (UTC)
            interval: "1m" または "5m"
            offer_side: "bid" または "ask"

        Returns:
            [{"timestamp": datetime, "open": float, "high": float, "low": float, "close": float, "volume": int}, ...]
        """
        if not self._check_dukascopy_available():
            logger.error("dukascopy-python is not available")
            return []

        instrument = self.get_dukascopy_instrument(symbol_id)
        if instrument is None:
            logger.error(f"Symbol not supported: {symbol_id}")
            return []

        try:
            import dukascopy_python

            # intervalをdukascopy形式に変換
            if interval == "1m":
                duka_interval = dukascopy_python.INTERVAL_MIN_1
            elif interval == "5m":
                duka_interval = dukascopy_python.INTERVAL_MIN_5
            else:
                logger.error(f"Unsupported interval: {interval}")
                return []

            # offer_side
            side = (
                dukascopy_python.OFFER_SIDE_BID
                if offer_side == "bid"
                else dukascopy_python.OFFER_SIDE_ASK
            )

            # UTCタイムゾーンを確認
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=UTC)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=UTC)

            logger.info(f"Fetching {symbol_id} from {start_time} to {end_time}, interval={interval}")

            # データ取得
            df = dukascopy_python.fetch(
                instrument=instrument,
                interval=duka_interval,
                offer_side=side,
                start=start_time,
                end=end_time,
            )

            if df is None or df.empty:
                logger.warning(f"No data returned for {symbol_id}")
                return []

            # DataFrameをリストに変換
            result = []
            for idx, row in df.iterrows():
                timestamp = idx if isinstance(idx, datetime) else pd.to_datetime(idx)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)

                result.append({
                    "timestamp": timestamp,
                    "open": round(float(row["open"]), 6) if pd.notna(row.get("open")) else None,
                    "high": round(float(row["high"]), 6) if pd.notna(row.get("high")) else None,
                    "low": round(float(row["low"]), 6) if pd.notna(row.get("low")) else None,
                    "close": round(float(row["close"]), 6) if pd.notna(row.get("close")) else None,
                    "volume": int(row.get("volume", 0)) if pd.notna(row.get("volume")) else 0,
                })

            logger.info(f"Fetched {len(result)} records for {symbol_id}")
            return result

        except Exception as e:
            logger.error(f"Error fetching {symbol_id} from Dukascopy: {e}")
            import traceback
            traceback.print_exc()
            return []

    def fetch_around_release_time(
        self,
        symbol_id: str,
        release_time: datetime,
        before_minutes: int = 60,
        after_minutes: int = 60,
        interval: str = "1m"
    ) -> Dict[str, Any]:
        """
        指標発表時刻の前後のデータを取得

        Args:
            symbol_id: 銘柄ID
            release_time: 発表時刻 (UTC)
            before_minutes: 発表前の分数 (デフォルト60分)
            after_minutes: 発表後の分数 (デフォルト60分)
            interval: "1m" または "5m"

        Returns:
            {
                "symbol_id": str,
                "release_time": str,
                "interval": str,
                "data": [...],
                "metadata": {
                    "before_minutes": int,
                    "after_minutes": int,
                    "data_count": int
                }
            }
        """
        if release_time.tzinfo is None:
            release_time = release_time.replace(tzinfo=UTC)

        start_time = release_time - timedelta(minutes=before_minutes)
        end_time = release_time + timedelta(minutes=after_minutes)

        data = self.fetch_intraday_data(
            symbol_id=symbol_id,
            start_time=start_time,
            end_time=end_time,
            interval=interval
        )

        # timestampをISO形式文字列に変換
        formatted_data = []
        for d in data:
            formatted_data.append({
                "timestamp": d["timestamp"].isoformat() if isinstance(d["timestamp"], datetime) else d["timestamp"],
                "open": d["open"],
                "high": d["high"],
                "low": d["low"],
                "close": d["close"],
                "volume": d["volume"],
            })

        return {
            "symbol_id": symbol_id,
            "release_time": release_time.isoformat(),
            "interval": interval,
            "data": formatted_data,
            "metadata": {
                "before_minutes": before_minutes,
                "after_minutes": after_minutes,
                "data_count": len(formatted_data),
            }
        }

    def save_to_db(
        self,
        symbol_id: str,
        data: List[Dict[str, Any]],
        interval: str
    ) -> int:
        """
        取得したデータをTimescaleDBに保存

        Args:
            symbol_id: 銘柄ID
            data: OHLCデータのリスト
            interval: "1m" または "5m"

        Returns:
            保存したレコード数
        """
        if not data:
            return 0

        try:
            count = market_repository.upsert_intraday_data(
                symbol_id=symbol_id,
                data=data,
                interval=interval,
                source="dukascopy"
            )
            logger.info(f"Saved {count} records for {symbol_id} ({interval}) to DB")
            return count
        except Exception as e:
            logger.error(f"Error saving {symbol_id} to DB: {e}")
            return 0

    def fetch_and_save(
        self,
        symbol_id: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = "1m"
    ) -> Dict[str, Any]:
        """
        データを取得してDBに保存

        Returns:
            {
                "symbol_id": str,
                "interval": str,
                "fetched": int,
                "saved": int,
                "success": bool
            }
        """
        data = self.fetch_intraday_data(
            symbol_id=symbol_id,
            start_time=start_time,
            end_time=end_time,
            interval=interval
        )

        saved = self.save_to_db(symbol_id, data, interval)

        return {
            "symbol_id": symbol_id,
            "interval": interval,
            "fetched": len(data),
            "saved": saved,
            "success": len(data) > 0 and saved > 0
        }

    def fetch_for_indicator_release(
        self,
        symbol_id: str,
        release_time: datetime
    ) -> Dict[str, Any]:
        """
        指標発表用に1分足・5分足両方を取得してDBに保存

        仕様:
        - 1分足: 発表前後1時間 (±60分)
        - 5分足: 発表前後24時間 (±1440分)

        Args:
            symbol_id: 銘柄ID
            release_time: 発表時刻 (UTC)

        Returns:
            {
                "symbol_id": str,
                "release_time": str,
                "1m": {"fetched": int, "saved": int},
                "5m": {"fetched": int, "saved": int}
            }
        """
        if release_time.tzinfo is None:
            release_time = release_time.replace(tzinfo=UTC)

        # 1分足: ±60分
        result_1m = self.fetch_and_save(
            symbol_id=symbol_id,
            start_time=release_time - timedelta(minutes=60),
            end_time=release_time + timedelta(minutes=60),
            interval="1m"
        )

        # 5分足: ±24時間
        result_5m = self.fetch_and_save(
            symbol_id=symbol_id,
            start_time=release_time - timedelta(hours=24),
            end_time=release_time + timedelta(hours=24),
            interval="5m"
        )

        return {
            "symbol_id": symbol_id,
            "release_time": release_time.isoformat(),
            "1m": {
                "fetched": result_1m["fetched"],
                "saved": result_1m["saved"]
            },
            "5m": {
                "fetched": result_5m["fetched"],
                "saved": result_5m["saved"]
            }
        }

    def bulk_fetch_for_releases(
        self,
        symbol_ids: List[str],
        release_times: List[datetime]
    ) -> List[Dict[str, Any]]:
        """
        複数銘柄×複数発表時刻のデータを一括取得

        Args:
            symbol_ids: 銘柄IDのリスト
            release_times: 発表時刻のリスト

        Returns:
            各組み合わせの取得結果リスト
        """
        results = []
        for symbol_id in symbol_ids:
            for release_time in release_times:
                result = self.fetch_for_indicator_release(symbol_id, release_time)
                results.append(result)
        return results

    # =========================================================================
    # バックグラウンド差分更新機能
    # =========================================================================

    def _execute_sync(
        self,
        symbol_id: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        update_sync_status: bool = True
    ) -> Dict[str, Any]:
        """
        同期処理の共通実装（フェッチ→保存→古いデータ削除→ステータス更新）

        Args:
            symbol_id: 銘柄ID
            interval: 足種 ("1m" or "5m")
            start_time: 開始日時 (UTC)
            end_time: 終了日時 (UTC)
            update_sync_status: 同期ステータスを更新するか

        Returns:
            {
                "success": bool,
                "fetched": int,
                "saved": int,
                "deleted": int,
                "error": str (エラー時のみ)
            }
        """
        try:
            # データ取得
            data = self.fetch_intraday_data(
                symbol_id=symbol_id,
                start_time=start_time,
                end_time=end_time,
                interval=interval
            )

            # 保存
            saved = self.save_to_db(symbol_id, data, interval)

            # 1年以上前のデータを削除
            one_year_ago = datetime.now(UTC) - timedelta(days=self.DATA_RETENTION_DAYS)
            deleted = market_repository.delete_old_intraday_data(
                symbol_id=symbol_id,
                interval=interval,
                before_date=one_year_ago
            )

            # 同期状態更新
            if update_sync_status:
                data_range = market_repository.get_intraday_data_range(symbol_id, interval)
                market_repository.upsert_sync_status(
                    symbol_id=symbol_id,
                    interval=interval,
                    last_sync_at=end_time,
                    data_start_date=data_range["min_timestamp"].date() if data_range else None,
                    data_end_date=data_range["max_timestamp"].date() if data_range else None,
                    record_count=data_range["count"] if data_range else 0,
                    sync_status="completed"
                )

            return {
                "success": True,
                "fetched": len(data),
                "saved": saved,
                "deleted": deleted
            }

        except Exception as e:
            logger.error(f"Error in _execute_sync for {symbol_id} {interval}: {e}")
            if update_sync_status:
                market_repository.upsert_sync_status(
                    symbol_id=symbol_id,
                    interval=interval,
                    sync_status="failed",
                    error_message=str(e)
                )
            return {
                "success": False,
                "fetched": 0,
                "saved": 0,
                "deleted": 0,
                "error": str(e)
            }

    def needs_sync(self, symbol_id: str, interval: str) -> bool:
        """
        同期が必要かどうかを判定（TTL 15日経過チェック）

        Returns:
            True: 同期が必要（15日以上経過 or 未同期）
            False: 同期不要
        """
        status = market_repository.get_sync_status(symbol_id, interval)

        if not status:
            return True

        if not status.get("last_sync_at"):
            return True

        # last_sync_atをdatetimeに変換
        last_sync = datetime.fromisoformat(status["last_sync_at"])
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=UTC)

        now = datetime.now(UTC)
        days_since_sync = (now - last_sync).days

        return days_since_sync >= self.SYNC_TTL_DAYS

    def get_intraday_data_with_background_sync(
        self,
        symbol_id: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        分足データを取得（必要に応じてバックグラウンドで同期開始）

        - DBにデータがあれば即座に返却
        - TTL経過していればバックグラウンドで差分更新を開始
        - DBにデータがなく、TTL経過していない場合は空を返却

        Returns:
            {
                "data": [...],
                "from_db": bool,
                "sync_triggered": bool,
                "sync_status": str
            }
        """
        # 同期状態を取得
        sync_status = market_repository.get_sync_status(symbol_id, interval)

        # DBからデータを取得
        db_data = market_repository.get_intraday_data(
            symbol_id=symbol_id,
            interval=interval,
            start_time=start_time,
            end_time=end_time
        )

        result = {
            "data": db_data,
            "from_db": len(db_data) > 0,
            "sync_triggered": False,
            "sync_status": sync_status.get("sync_status") if sync_status else "pending"
        }

        # 同期が必要かチェック
        if self.needs_sync(symbol_id, interval):
            # バックグラウンドで同期開始
            self._trigger_background_sync(symbol_id, interval)
            result["sync_triggered"] = True

        return result

    def _trigger_background_sync(self, symbol_id: str, interval: str) -> bool:
        """
        バックグラウンドで差分同期を開始

        Returns:
            True: 新しいタスクを開始した
            False: 既に実行中
        """
        task_key = f"{symbol_id}_{interval}"

        with self._lock:
            # 既に実行中かチェック
            if task_key in self._background_tasks:
                thread = self._background_tasks[task_key]
                if thread.is_alive():
                    logger.info(f"Background sync already running for {task_key}")
                    return False

            # 新しいスレッドを開始
            thread = threading.Thread(
                target=self._sync_one_year_data,
                args=(symbol_id, interval),
                daemon=True
            )
            self._background_tasks[task_key] = thread
            thread.start()
            logger.info(f"Started background sync for {task_key}")
            return True

    def _sync_one_year_data(self, symbol_id: str, interval: str) -> None:
        """
        1年分のデータを差分同期（バックグラウンド実行用）

        処理フロー:
        1. 同期状態をsyncingに更新
        2. 最終同期日時〜現在 の差分を取得（共通関数使用）
        3. 同期状態をcompletedに更新
        """
        task_key = f"{symbol_id}_{interval}"
        logger.info(f"[{task_key}] Starting 1-year data sync...")

        try:
            # 1. 同期状態をsyncingに更新
            market_repository.upsert_sync_status(
                symbol_id=symbol_id,
                interval=interval,
                sync_status="syncing"
            )

            now = datetime.now(UTC)
            one_year_ago = now - timedelta(days=self.DATA_RETENTION_DAYS)

            # 差分取得の開始日時を決定
            data_range = market_repository.get_intraday_data_range(symbol_id, interval)
            if data_range and data_range.get("max_timestamp"):
                # 既存データがある場合: 最終データ日時から取得
                start_time = data_range["max_timestamp"]
                logger.info(f"[{task_key}] Incremental sync from {start_time}")
            else:
                # 初回: 1年前から取得
                start_time = one_year_ago
                logger.info(f"[{task_key}] Full sync from {start_time}")

            # 2. 共通関数で同期実行
            result = self._execute_sync(
                symbol_id=symbol_id,
                interval=interval,
                start_time=start_time,
                end_time=now,
                update_sync_status=True
            )

            if result["success"]:
                logger.info(f"[{task_key}] Sync completed: fetched={result['fetched']}, saved={result['saved']}, deleted={result['deleted']}")
            else:
                logger.error(f"[{task_key}] Sync failed: {result.get('error', 'unknown error')}")

        except Exception as e:
            logger.error(f"[{task_key}] Sync failed: {e}")
            import traceback
            traceback.print_exc()

            # エラー状態を記録
            market_repository.upsert_sync_status(
                symbol_id=symbol_id,
                interval=interval,
                sync_status="failed",
                error_message=str(e)
            )

        finally:
            # タスク完了後にクリーンアップ
            with self._lock:
                if task_key in self._background_tasks:
                    del self._background_tasks[task_key]

    def sync_symbol_data(
        self,
        symbol_id: str,
        intervals: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        銘柄の分足データを同期（同期的に実行）

        Args:
            symbol_id: 銘柄ID
            intervals: 対象足種リスト（デフォルト: ["1m", "5m"]）

        Returns:
            {
                "symbol_id": str,
                "results": {
                    "1m": {"success": bool, "fetched": int, "saved": int},
                    "5m": {...}
                }
            }
        """
        if intervals is None:
            intervals = ["1m", "5m"]

        results = {}
        now = datetime.now(UTC)
        one_year_ago = now - timedelta(days=self.DATA_RETENTION_DAYS)

        for interval in intervals:
            logger.info(f"Syncing {symbol_id} {interval}...")
            # 共通関数で同期実行
            results[interval] = self._execute_sync(
                symbol_id=symbol_id,
                interval=interval,
                start_time=one_year_ago,
                end_time=now,
                update_sync_status=True
            )

        return {
            "symbol_id": symbol_id,
            "results": results
        }

    def get_sync_status_all(self) -> List[Dict[str, Any]]:
        """全銘柄の同期状態を取得"""
        return market_repository.get_all_sync_status()

    def get_sync_status(self, symbol_id: str, interval: str) -> Optional[Dict[str, Any]]:
        """指定銘柄の同期状態を取得"""
        return market_repository.get_sync_status(symbol_id, interval)


# シングルトンインスタンス
dukascopy_service = DukascopyService()
