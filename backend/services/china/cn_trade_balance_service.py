"""
中国 貿易収支（Trade Balance）サービス

5系列:
- 貿易収支: 億USD
- 輸出額: 億USD
- 輸入額: 億USD
- 輸出 前年比 (%)
- 輸入 前年比 (%)
+ 前月増減幅（貿易収支のlevelから計算）

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート）
  indicators: cn_trade_balance, cn_exports, cn_imports, cn_exports_yoy, cn_imports_yoy
- FMP: 次回発表日の取得のみ

貿易収支データは税関（海关总署）が公表するため、NBSプレスリリースには含まれない。
DB蓄積データ（CSVインポート）のみで運用する。
レベル指標は1000 USD → 億USDに変換済み（CSVインポート時）。
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# パス定義
_BASE_DIR = Path(__file__).parent.parent.parent
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "economy"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_trade_balance_cache.json")

REDIS_KEY = "china:cn_trade_balance:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_trade_balance"

# DB指標ID
DB_INDICATORS = {
    "balance": "cn_trade_balance",
    "exports": "cn_exports",
    "imports": "cn_imports",
    "exports_yoy": "cn_exports_yoy",
    "imports_yoy": "cn_imports_yoy",
}

# レベル指標（1000 USD → 億 USD 変換対象）
_LEVEL_INDICATORS = {"cn_trade_balance", "cn_exports", "cn_imports"}

# 手動CSV（税関の正式レベル値）と mtime マーカー
_MANUAL_CSV_PATH = _BASE_DIR / "data" / "csv_import" / "中国貿易収支.csv"
_CSV_MTIME_MARKER = _FILE_CACHE_DIR / ".cn_trade_csv_mtime"

# 手動CSVの列名 → DB指標ID（import_nbs_trade_csv.py と一致）
_CSV_TRADE_MAP = {
    "Balance of Imports and Exports Current Period(1000 US dollars)": "cn_trade_balance",
    "Total Value of Exports Current Period(1000 US dollars)": "cn_exports",
    "Total Value of Imports Current Period(1000 US dollars)": "cn_imports",
    "Total Value of Exports Growth Rate (The same period last year=100)(%)": "cn_exports_yoy",
    "Total Value of Imports Growth Rate (The same period last year=100)(%)": "cn_imports_yoy",
}


def _import_manual_csv() -> None:
    """手動CSV（data/csv_import/中国貿易収支.csv）が更新されていれば再インポート。

    貿易(税関)のレベル値は自動取得源が無いため、税関の正式値を手動CSVで反映する
    （特に中国が1-2月を合算発表する1-2月分は FMP由来の再構成では復元できないため、
    正確な値はこのCSVが権威ソース）。mtime 検知で更新時のみ再取込・冪等。
    レベル指標は 1000 USD → 億 USD に変換（importスクリプトと同一処理）。
    """
    if not _MANUAL_CSV_PATH.exists():
        return
    try:
        mtime = os.path.getmtime(_MANUAL_CSV_PATH)
        last = 0.0
        if _CSV_MTIME_MARKER.exists():
            try:
                last = float(_CSV_MTIME_MARKER.read_text().strip())
            except (ValueError, OSError):
                last = 0.0
        if mtime <= last:
            return

        from scripts.import_nbs_pmi_csv import parse_csv_transposed
        from services.china.nbs_db_utils import upsert_nbs_data

        parsed = parse_csv_transposed(_MANUAL_CSV_PATH, _CSV_TRADE_MAP)
        for db_indicator, values in parsed.items():
            if not values:
                continue
            if db_indicator in _LEVEL_INDICATORS:
                values = {k: round(v / 100_000, 2) for k, v in values.items()}
            upsert_nbs_data(db_indicator, values, source="csv")

        os.makedirs(_FILE_CACHE_DIR, exist_ok=True)
        _CSV_MTIME_MARKER.write_text(str(mtime))
        logger.info(f"[Trade] Manual CSV re-imported (mtime={mtime})")
    except Exception as e:
        logger.warning(f"[Trade] Manual CSV import failed: {e}")


def _fetch_and_upsert() -> None:
    """FMP から YoY を gap-fill し、レベルは YoY×前年同月から再構成して補完。

    貿易(税関)データは自動取得源が無く、FMP economic_calendar_events(CN) の
    **YoY actual のみ信頼可能**（レベルの actual は単位不整合(M/B混在)で使用不可）。
    レベル系列は `level[m] = level[m-12months] * (1 + yoy[m]/100)`、
    `balance = exports - imports` で復元する。これは YoY の定義そのものであり、
    前年同月の実値が DB にあれば誤差 < 0.05%（検証済）。
    ただし中国は **1-2月を合算発表**し Feb の YoY が累計値のため、レベル再構成は
    単月が確定する **month >= 3 のみ**（1-2月分は手動CSVが担当）。冪等・欠損月のみ。
    """
    from datetime import datetime as _dt
    from services.china.nbs_db_utils import (
        backfill_from_fmp_events, load_nbs_data, upsert_nbs_data,
    )

    # 1. YoY を FMP から gap-fill（既存値は非上書き）
    backfill_from_fmp_events("cn_exports_yoy", "Exports YoY")
    backfill_from_fmp_events("cn_imports_yoy", "Imports YoY")

    # 2. レベル(輸出/輸入)を YoY×前年同月 から再構成（欠損月・単月のみ）
    for level_ind, yoy_ind in (("cn_exports", "cn_exports_yoy"), ("cn_imports", "cn_imports_yoy")):
        levels = load_nbs_data(level_ind)
        yoys = load_nbs_data(yoy_ind)
        recon: Dict[str, float] = {}
        for date_str, yoy in yoys.items():
            if date_str in levels:
                continue
            try:
                d = _dt.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if d.month <= 2:  # 中国1-2月合算 → 単月再構成不可（手動CSV管轄）
                continue
            prev = f"{d.year - 1}-{d.month:02d}-01"
            base = levels.get(prev)
            if base is None:
                continue
            recon[date_str] = round(base * (1 + yoy / 100), 2)
        if recon:
            upsert_nbs_data(level_ind, recon, source="api")

    # 3. 貿易収支 = 輸出 - 輸入（両レベルが揃う欠損月のみ）
    exports = load_nbs_data("cn_exports")
    imports = load_nbs_data("cn_imports")
    balance = load_nbs_data("cn_trade_balance")
    recon_bal: Dict[str, float] = {}
    for date_str, exp_val in exports.items():
        if date_str in balance:
            continue
        imp_val = imports.get(date_str)
        if imp_val is None:
            continue
        recon_bal[date_str] = round(exp_val - imp_val, 2)
    if recon_bal:
        upsert_nbs_data("cn_trade_balance", recon_bal, source="api")


def _build_data() -> Dict[str, Any]:
    """DBからデータを読み込み（手動CSV + FMP YoY + レベル再構成で蓄積）"""
    from services.china.nbs_db_utils import load_nbs_multi

    # --- 手動CSV（税関の正式値）→ DB蓄積（mtime更新時のみ・権威ソース）---
    try:
        _import_manual_csv()
    except Exception as e:
        logger.warning(f"[Trade] Manual CSV import failed: {e}")

    # --- FMP YoY gap-fill + レベル再構成 → DB蓄積 ---
    try:
        _fetch_and_upsert()
    except Exception as e:
        logger.warning(f"[Trade] FMP fetch/reconstruct failed: {e}")

    # --- DBから全データ読み込み ---
    all_indicators = list(DB_INDICATORS.values())
    db_data = load_nbs_multi(all_indicators)

    balance_data = db_data.get(DB_INDICATORS["balance"], {})
    exports_data = db_data.get(DB_INDICATORS["exports"], {})
    imports_data = db_data.get(DB_INDICATORS["imports"], {})
    exports_yoy_data = db_data.get(DB_INDICATORS["exports_yoy"], {})
    imports_yoy_data = db_data.get(DB_INDICATORS["imports_yoy"], {})

    logger.info(
        f"[Trade] DB records: balance={len(balance_data)}, "
        f"exports={len(exports_data)}, imports={len(imports_data)}, "
        f"exports_yoy={len(exports_yoy_data)}, imports_yoy={len(imports_yoy_data)}"
    )

    # 貿易収支水準データ
    balance_list = [{"date": d, "value": round(v, 2)} for d, v in sorted(balance_data.items())]
    exports_list = [{"date": d, "value": round(v, 2)} for d, v in sorted(exports_data.items())]
    imports_list = [{"date": d, "value": round(v, 2)} for d, v in sorted(imports_data.items())]

    # 前年比
    exports_yoy_list = [{"date": d, "value": round(v, 1)} for d, v in sorted(exports_yoy_data.items())]
    imports_yoy_list = [{"date": d, "value": round(v, 1)} for d, v in sorted(imports_yoy_data.items())]

    # 貿易収支 前年比（レベルから計算）
    balance_yoy_list = _calc_yoy_from_level(balance_data)

    # 前月増減幅（貿易収支レベルから計算）
    balance_mom_diff = _calc_mom_diff(balance_data)
    exports_mom_diff = _calc_mom_diff(exports_data)
    imports_mom_diff = _calc_mom_diff(imports_data)

    return {
        "balance": balance_list,
        "exports": exports_list,
        "imports": imports_list,
        "balance_yoy": balance_yoy_list,
        "exports_yoy": exports_yoy_list,
        "imports_yoy": imports_yoy_list,
        "balance_mom_diff": balance_mom_diff,
        "exports_mom_diff": exports_mom_diff,
        "imports_mom_diff": imports_mom_diff,
        "latest_balance": balance_list[-1] if balance_list else None,
        "latest_exports": exports_list[-1] if exports_list else None,
        "latest_imports": imports_list[-1] if imports_list else None,
    }


def _calc_mom_diff(data: Dict[str, float]) -> List[Dict[str, Any]]:
    """前月増減幅を計算"""
    sorted_dates = sorted(data.keys())
    result = []
    for i in range(1, len(sorted_dates)):
        curr_date = sorted_dates[i]
        prev_date = sorted_dates[i - 1]
        diff = data[curr_date] - data[prev_date]
        result.append({"date": curr_date, "value": round(diff, 2)})
    return result


def _calc_yoy_from_level(data: Dict[str, float]) -> List[Dict[str, Any]]:
    """レベルデータから前年比(%)を計算"""
    from datetime import datetime as dt
    result = []
    for date_str, current_val in sorted(data.items()):
        d = dt.strptime(date_str, "%Y-%m-%d")
        prev_year_date = f"{d.year - 1}-{d.month:02d}-01"
        if prev_year_date in data:
            prev_val = data[prev_year_date]
            if prev_val != 0:
                yoy = ((current_val - prev_val) / abs(prev_val)) * 100
                result.append({"date": date_str, "value": round(yoy, 1)})
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[Trade] Failed to get next release: {e}")
        return None


class CnTradeBalanceService:
    """中国貿易収支サービス"""

    def __init__(self):
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_timeout=2, socket_connect_timeout=2)
                self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def _from_redis(self) -> Optional[Dict[str, Any]]:
        r = self._get_redis()
        if not r:
            return None
        try:
            raw = r.get(REDIS_KEY)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def _to_redis(self, payload: Dict[str, Any]) -> None:
        r = self._get_redis()
        if not r:
            return
        try:
            r.setex(REDIS_KEY, REDIS_TTL, json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    def _from_file(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(FILE_CACHE_PATH):
            return None
        try:
            with open(FILE_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _to_file(self, payload: Dict[str, Any]) -> None:
        os.makedirs(_FILE_CACHE_DIR, exist_ok=True)
        try:
            with open(FILE_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[Trade] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        next_release = _get_next_release()

        return {
            **data,
            "metadata": {
                "indicator": "Trade Balance",
                "source": "General Administration of Customs / NBS",
                "unit": "100 million USD",
                "series": {
                    "balance": "貿易収支 (億USD)",
                    "exports": "輸出額 (億USD)",
                    "imports": "輸入額 (億USD)",
                    "exports_yoy": "輸出 前年比 (%)",
                    "imports_yoy": "輸入 前年比 (%)",
                },
                "total_records": len(data.get("balance", [])),
                "last_fetched": datetime.now(JST).isoformat(),
            },
            "next_release": next_release,
        }

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データ取得（キャッシュ優先）"""
        if not force_refresh:
            cached = self._from_redis()
            if cached:
                return cached
            cached = self._from_file()
            if cached:
                self._to_redis(cached)
                return cached

        payload = self._build_payload()
        self._to_redis(payload)
        self._to_file(payload)
        return payload

    def invalidate_cache(self) -> Dict[str, Any]:
        r = self._get_redis()
        if r:
            try:
                r.delete(REDIS_KEY)
            except Exception:
                pass
        if os.path.exists(FILE_CACHE_PATH):
            os.remove(FILE_CACHE_PATH)
        return {"success": True, "message": "Trade Balance cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        r = self._get_redis()
        redis_exists = False
        redis_ttl = None
        if r:
            try:
                redis_exists = bool(r.exists(REDIS_KEY))
                redis_ttl = r.ttl(REDIS_KEY)
            except Exception:
                pass
        file_exists = os.path.exists(FILE_CACHE_PATH)
        file_mtime = None
        if file_exists:
            file_mtime = datetime.fromtimestamp(
                os.path.getmtime(FILE_CACHE_PATH), tz=JST
            ).isoformat()
        return {
            "redis": {"exists": redis_exists, "ttl_seconds": redis_ttl},
            "file": {"exists": file_exists, "last_modified": file_mtime},
        }


# シングルトン
cn_trade_balance_service = CnTradeBalanceService()
