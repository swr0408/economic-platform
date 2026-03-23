"""
日経225オプション データサービス

データソース (優先順位):
  1. ose{yyyymmdd}tp.csv: オプション理論価格 (ATM IV, スマイル, スキュー)
  2. rb{yyyymmdd}.csv: 清算値, 理論価格, 原資産価格, DTE
  3. {yyyymmdd}open_interest.xlsx: 建玉残高 (前日OI含む)
  4. {yyyymmdd}_market_data_whole_day.xlsx: 日通し出来高サマリー

ローカルファイル: backend/data/nikkei_option_data/ から最新2営業日を自動判定
URL取得: JPX公式サイトからフォールバック

提供データ:
  - ATM IV ターム構造（各限月のATM IV + 前日比）
  - ATM IV 時系列（日次蓄積）
  - IV スマイル/スキュー（行使価格別IV + 前日比）
  - 25D Risk Reversal / Butterfly
  - 建玉分布（行使価格別 + 前日差）
  - 出来高分布（行使価格別）
  - 集計統計（OI合計, 出来高合計, 5日平均）

更新スケジュール:
  - 日次 (JST 17:00) Settlement CSV取得
  - 日次 (JST 20:30) OI XLSX取得・マージ
"""
import io
import json
import logging
import math
import re
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# ========== パス ==========
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_CACHE_FILE = CACHE_DIR / "nikkei225_options_cache.json"
ATM_IV_HISTORY_FILE = CACHE_DIR / "nikkei225_options_atm_iv_history.json"

LOCAL_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "nikkei_option_data"

# Redis
SNAPSHOT_CACHE_KEY = "market:nikkei225_options:data"
ATM_IV_HISTORY_KEY = "market:nikkei225_options:atm_iv_history"

# URLs (フォールバック用)
SETTLEMENT_CSV_URL = (
    "https://www.jpx.co.jp/markets/derivatives/settlement-price/"
    "tvdivq00000014l6-att/rb{date}.csv"
)
OPEN_INTEREST_URL = (
    "https://www.jpx.co.jp/markets/derivatives/trading-volume/"
    "tvdivq00000014nn-att/{date}open_interest.xlsx"
)
MARKET_DATA_URL = (
    "https://www.jpx.co.jp/markets/derivatives/trading-volume/"
    "tvdivq00000014nn-att/{date}_market_data_whole_day.xlsx"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Regex patterns
ISSUE_NAME_RE = re.compile(r"(PUT|CAL)_225_(\d{6})_(\d+)")
OI_ISSUE_RE = re.compile(r"NIKKEI\s+225\s+([PC])(\d{4})-(\d+)")

# File name patterns for local data
LOCAL_FILE_PATTERNS = {
    "ose_tp": re.compile(r"ose(\d{8})tp\.csv"),
    "rb": re.compile(r"rb(\d{8})\.csv"),
    "oi": re.compile(r"(\d{8})open_interest\.xlsx"),
    "market_data": re.compile(r"(\d{8})_market_data_whole_day\.xlsx"),
}


# ========== ユーティリティ ==========

def _prev_business_day(d: date) -> date:
    """前営業日を返す（土日スキップ）"""
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def _safe_float(val: Any) -> Optional[float]:
    """安全にfloat変換"""
    if val is None:
        return None
    try:
        s = str(val).strip().replace(",", "")
        if not s or s in ("", "-", "nan", "NaN"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    """安全にint変換"""
    f = _safe_float(val)
    if f is None:
        return None
    return int(f)


def _filter_iv(iv: Optional[float]) -> Optional[float]:
    """
    IV品質フィルタ:
    - 0% < IV < 150% の範囲外はnullとする
    - IV == 0.01% (1bp) は JPX の下限固定値のため除外
    """
    if iv is None:
        return None
    if iv <= 0.01 or iv > 150.0:
        return None
    return round(iv, 4)


def _quality_flag(strike: int, underlying: float) -> str:
    """
    品質フラグ:
    - good: ATM ± 10% (信頼性の高いIV)
    - fair: ATM ± 20%
    - distant: それ以外 (深いOTM、IV信頼性低)
    """
    if underlying <= 0:
        return "distant"
    moneyness = abs(strike - underlying) / underlying
    if moneyness < 0.10:
        return "good"
    elif moneyness < 0.20:
        return "fair"
    return "distant"


def _interpolate_iv(
    strikes_list: List[Dict], target_strike: float, iv_key: str
) -> Optional[float]:
    """
    線形補間でターゲットストライクのIVを推定

    strikes_listはstrike昇順ソート済みの辞書リスト。
    iv_keyは 'put_iv' or 'call_iv'。
    ターゲットストライクの両側の最近接ストライクを見つけて線形補間する。
    """
    valid = [(s["strike"], s[iv_key]) for s in strikes_list
             if s.get(iv_key) is not None and s[iv_key] > 0]
    if not valid:
        return None

    # ターゲットストライクに一致するものがあればそのまま返す
    for k, iv in valid:
        if abs(k - target_strike) < 1:
            return iv

    # 両側を探す
    lower = [(k, iv) for k, iv in valid if k < target_strike]
    upper = [(k, iv) for k, iv in valid if k > target_strike]

    if lower and upper:
        k1, iv1 = max(lower, key=lambda x: x[0])
        k2, iv2 = min(upper, key=lambda x: x[0])
        if k2 == k1:
            return iv1
        ratio = (target_strike - k1) / (k2 - k1)
        return iv1 + ratio * (iv2 - iv1)
    elif lower:
        return max(lower, key=lambda x: x[0])[1]
    elif upper:
        return min(upper, key=lambda x: x[0])[1]
    return None


class Nikkei225OptionsService:
    """日経225オプション データサービス"""

    def _should_refresh(self) -> bool:
        """キャッシュの更新が必要かどうか判定（6時間TTL）"""
        try:
            cached = redis_client.get(SNAPSHOT_CACHE_KEY)
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
        """オプションデータを取得"""
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
            logger.error(f"[NK225Options] Build error: {e}")
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
            "data": None,
            "latest": None,
            "metadata": {"source": "JPX Nikkei 225 Options"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    # ========== ローカルファイル探索 ==========

    def _discover_local_dates(self) -> List[Tuple[str, Dict[str, Optional[Path]]]]:
        """
        ローカルデータディレクトリから利用可能な日付を探索

        前営業日探索ロジック:
        - ファイル名から日付を正規表現で抽出
        - 日付でグルーピング → 新しい順にソート
        - 祝日・週跨ぎでも、ファイル名ベースで正しく前営業日を判定
        - 最大5日分を返す（通常は最新2日分を使用）
        """
        if not LOCAL_DATA_DIR.exists():
            return []

        date_files: Dict[str, Dict[str, Optional[Path]]] = {}

        for path in LOCAL_DATA_DIR.iterdir():
            if not path.is_file():
                continue
            name = path.name
            for file_key, pattern in LOCAL_FILE_PATTERNS.items():
                m = pattern.match(name)
                if m:
                    date_str = m.group(1)
                    if date_str not in date_files:
                        date_files[date_str] = {
                            "ose_tp": None, "rb": None,
                            "oi": None, "market_data": None,
                        }
                    date_files[date_str][file_key] = path
                    break

        result = sorted(date_files.items(), key=lambda x: x[0], reverse=True)
        return result[:5]

    # ========== ose*tp.csv パーサー ==========

    def _parse_ose_tp_csv(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        ose*tp.csv（オプション理論価格）をパース

        CSVレイアウト (17列, ASCII, ヘッダーなし):
          Col 0: Product code ("NK225E")  Col 1: Type ("OOP"=option)
          Col 2: Contract month (202604)  Col 3: Strike (53500.0)
          Col 5: Put issue code           Col 6: Put settlement
          Col 8: Put theoretical          Col 9: Put IV (decimal: 0.305829)
          Col 10: Call issue code         Col 11: Call settlement
          Col 13: Call theoretical        Col 14: Call IV (decimal)
          Col 15: Underlying (53700.39)   Col 16: Interest rate (0.3144)

        IVは小数形式 → ×100 で%に変換
        Put/Call が同一行にあるため rb.csv より効率的にパース可能
        """
        import pandas as pd

        try:
            df = pd.read_csv(file_path, header=None)
        except Exception as e:
            logger.error(f"[NK225Options] Failed to read ose_tp CSV: {e}")
            return None

        # NK225 option rows only
        nk = df[(df[0].astype(str).str.strip() == "NK225E") & (df[1] == "OOP")]
        if nk.empty:
            return None

        underlying_price = _safe_float(nk.iloc[0, 15])
        interest_rate = _safe_float(nk.iloc[0, 16])

        if underlying_price is None or underlying_price <= 0:
            return None

        expiries_dict: Dict[str, Dict] = {}

        for _, row in nk.iterrows():
            contract_month = str(int(row[2]))
            strike = int(row[3])

            put_iv_raw = _safe_float(row[9])
            call_iv_raw = _safe_float(row[14])
            # IV: decimal → percentage
            put_iv = _filter_iv(put_iv_raw * 100 if put_iv_raw is not None else None)
            call_iv = _filter_iv(call_iv_raw * 100 if call_iv_raw is not None else None)

            if contract_month not in expiries_dict:
                expiries_dict[contract_month] = {"strikes_map": {}}

            expiries_dict[contract_month]["strikes_map"][strike] = {
                "strike": strike,
                "put_settlement": _safe_float(row[6]),
                "put_theoretical": _safe_float(row[8]),
                "put_iv": put_iv,
                "call_settlement": _safe_float(row[11]),
                "call_theoretical": _safe_float(row[13]),
                "call_iv": call_iv,
                "put_oi": None,
                "call_oi": None,
                "put_volume": None,
                "call_volume": None,
                "prev_put_iv": None,
                "prev_call_iv": None,
                "prev_put_oi": None,
                "prev_call_oi": None,
                "oi_change_put": None,
                "oi_change_call": None,
                "quality": _quality_flag(strike, underlying_price),
            }

        return {
            "underlying_price": underlying_price,
            "interest_rate": interest_rate,
            "expiries_dict": expiries_dict,
        }

    # ========== rb.csv パーサー ==========

    def _extract_expiry_mapping(self, rb_path: Path) -> Dict[str, Dict]:
        """
        rb.csv から contract_month → {expiry_date, dte} マッピングを抽出

        ose*tp.csv にはDTE/expiry_dateが含まれないため、
        rb.csv の Issue Name (例: PUT_225_260409_53500) から抽出する。

        Returns:
            {"202604": {"expiry_date": "2026-04-09", "dte": 24}, ...}
        """
        import pandas as pd

        try:
            try:
                df = pd.read_csv(rb_path, encoding="shift_jis", skiprows=2)
            except UnicodeDecodeError:
                df = pd.read_csv(rb_path, encoding="cp932", skiprows=2)
        except Exception as e:
            logger.error(f"[NK225Options] Failed to read rb CSV: {e}")
            return {}

        if df.empty or len(df.columns) < 12:
            return {}

        col_issue_name = df.columns[1]
        col_contract_month = df.columns[3]
        col_dte = df.columns[10]

        mapping: Dict[str, Dict] = {}

        for _, row in df.iterrows():
            issue_name = str(row.get(col_issue_name, "")).strip()
            m = ISSUE_NAME_RE.match(issue_name)
            if not m:
                continue

            expiry_yymmdd = m.group(2)
            contract_month = str(row.get(col_contract_month, "")).strip()
            dte = _safe_int(row.get(col_dte))

            if contract_month and contract_month not in mapping:
                try:
                    yy = int(expiry_yymmdd[:2])
                    mm_exp = int(expiry_yymmdd[2:4])
                    dd_exp = int(expiry_yymmdd[4:6])
                    expiry_date = f"20{yy:02d}-{mm_exp:02d}-{dd_exp:02d}"
                    mapping[contract_month] = {
                        "expiry_date": expiry_date,
                        "dte": dte,
                    }
                except (ValueError, IndexError):
                    continue

        return mapping

    def _extract_underlying_from_rb(self, rb_path: Path) -> Optional[float]:
        """rb.csv から原資産価格のみを高速抽出"""
        import pandas as pd

        try:
            try:
                df = pd.read_csv(rb_path, encoding="shift_jis", skiprows=2, nrows=50)
            except UnicodeDecodeError:
                df = pd.read_csv(rb_path, encoding="cp932", skiprows=2, nrows=50)
        except Exception:
            return None

        if df.empty or len(df.columns) < 8:
            return None

        col_issue = df.columns[1]
        col_underlying = df.columns[7]
        mask = df[col_issue].astype(str).str.contains("_225_", na=False)
        vals = df.loc[mask, col_underlying].dropna()
        if len(vals) > 0:
            return _safe_float(vals.iloc[0])
        return None

    def _parse_rb_csv_full(self, rb_path: Path) -> Optional[Dict[str, Any]]:
        """rb.csv をフルパースして構造化データを返す（ose*tp.csvがない場合のフォールバック）"""
        import pandas as pd

        try:
            try:
                df = pd.read_csv(rb_path, encoding="shift_jis", skiprows=2)
            except UnicodeDecodeError:
                df = pd.read_csv(rb_path, encoding="cp932", skiprows=2)
        except Exception as e:
            logger.error(f"[NK225Options] Failed to read rb CSV: {e}")
            return None

        if df.empty or len(df.columns) < 12:
            return None

        # Filter NK225 options
        issue_col = df.columns[1]
        mask = df[issue_col].astype(str).str.contains(
            "PUT_225_|CAL_225_", regex=True, na=False
        )
        nk225_df = df[mask].copy()
        if nk225_df.empty:
            return None

        col_issue_name = df.columns[1]
        col_contract_month = df.columns[3]
        col_strike = df.columns[4]
        col_settlement = df.columns[5]
        col_theoretical = df.columns[6]
        col_underlying_price = df.columns[7]
        col_iv = df.columns[8]
        col_dte = df.columns[10]

        underlying_price = None
        vals = nk225_df[col_underlying_price].dropna()
        if len(vals) > 0:
            underlying_price = _safe_float(vals.iloc[0])
        if underlying_price is None or underlying_price <= 0:
            return None

        expiries_dict: Dict[str, Dict] = {}

        for _, row in nk225_df.iterrows():
            issue_name = str(row.get(col_issue_name, "")).strip()
            m = ISSUE_NAME_RE.match(issue_name)
            if not m:
                continue

            pc_type = m.group(1)
            expiry_yymmdd = m.group(2)
            strike = int(m.group(3))
            contract_month = str(row.get(col_contract_month, "")).strip()

            try:
                yy = int(expiry_yymmdd[:2])
                mm_exp = int(expiry_yymmdd[2:4])
                dd_exp = int(expiry_yymmdd[4:6])
                expiry_date = f"20{yy:02d}-{mm_exp:02d}-{dd_exp:02d}"
            except (ValueError, IndexError):
                continue

            settlement = _safe_float(row.get(col_settlement))
            theoretical = _safe_float(row.get(col_theoretical))
            iv = _filter_iv(_safe_float(row.get(col_iv)))
            dte = _safe_int(row.get(col_dte))

            if contract_month not in expiries_dict:
                expiries_dict[contract_month] = {
                    "expiry_date": expiry_date,
                    "dte": dte,
                    "strikes_map": {},
                }

            sd = expiries_dict[contract_month]["strikes_map"].setdefault(
                strike, {
                    "strike": strike,
                    "put_settlement": None, "put_theoretical": None, "put_iv": None,
                    "call_settlement": None, "call_theoretical": None, "call_iv": None,
                    "put_oi": None, "call_oi": None,
                    "put_volume": None, "call_volume": None,
                    "prev_put_iv": None, "prev_call_iv": None,
                    "prev_put_oi": None, "prev_call_oi": None,
                    "oi_change_put": None, "oi_change_call": None,
                    "quality": _quality_flag(strike, underlying_price),
                }
            )

            if pc_type == "PUT":
                sd["put_settlement"] = settlement
                sd["put_theoretical"] = theoretical
                sd["put_iv"] = iv
            else:
                sd["call_settlement"] = settlement
                sd["call_theoretical"] = theoretical
                sd["call_iv"] = iv

        return {
            "underlying_price": underlying_price,
            "interest_rate": None,
            "expiries_dict": expiries_dict,
        }

    # ========== OI パーサー ==========

    def _parse_oi_local(self, file_path: Path) -> Optional[Dict]:
        """
        open_interest.xlsx をパース（前日OI・OI変化を含む）

        OI XLSX "Detail 1" レイアウト (固定列):
          Put: Col 0=Issue, Col 1=Volume, Col 2=OI, Col 3=OI Change, Col 4=Prev OI
          Call: Col 6=Issue, Col 7=Volume, Col 8=OI, Col 9=OI Change, Col 10=Prev OI
        """
        import pandas as pd

        try:
            df = pd.read_excel(file_path, sheet_name=1, header=None, engine="openpyxl")
        except Exception as e:
            logger.error(f"[NK225Options] Failed to read OI XLSX: {e}")
            return None

        result: Dict[tuple, Dict] = {}

        # Put: (name=0, vol=1, oi=2, change=3, prev_oi=4)
        # Call: (name=6, vol=7, oi=8, change=9, prev_oi=10)
        put_call_cols = [
            (0, 1, 2, 3, 4),
            (6, 7, 8, 9, 10),
        ]

        for idx in range(df.shape[0]):
            for name_col, vol_col, oi_col, change_col, prev_oi_col in put_call_cols:
                if name_col >= df.shape[1]:
                    continue
                cell_val = str(df.iloc[idx, name_col]).strip()
                m = OI_ISSUE_RE.search(cell_val)
                if m:
                    pc = m.group(1)
                    contract_month = m.group(2)
                    strike = int(m.group(3))

                    volume = _safe_int(df.iloc[idx, vol_col]) if vol_col < df.shape[1] else None
                    oi = _safe_int(df.iloc[idx, oi_col]) if oi_col < df.shape[1] else None
                    oi_change = _safe_int(df.iloc[idx, change_col]) if change_col < df.shape[1] else None
                    prev_oi = _safe_int(df.iloc[idx, prev_oi_col]) if prev_oi_col < df.shape[1] else None

                    key = (contract_month, strike, pc)
                    result[key] = {
                        "oi": oi,
                        "volume": volume,
                        "oi_change": oi_change,
                        "prev_oi": prev_oi,
                    }

        return result if result else None

    # ========== Market Data Volume パーサー ==========

    def _parse_market_data_volume(self, file_path: Path) -> Optional[Dict]:
        """
        market_data_whole_day.xlsx から NK225オプション合計出来高を取得

        Sheet 4 (Options), Row 14: NK225 Options
          Col 13 = Put Volume, Col 17 = Call Volume, Col 21 = Total
        """
        import pandas as pd

        try:
            df = pd.read_excel(file_path, sheet_name=4, header=None, engine="openpyxl")
        except Exception as e:
            logger.debug(f"[NK225Options] Failed to read market data XLSX: {e}")
            return None

        if df.shape[0] < 15:
            return None

        return {
            "put_volume": _safe_int(df.iloc[14, 13]) if df.shape[1] > 13 else None,
            "call_volume": _safe_int(df.iloc[14, 17]) if df.shape[1] > 17 else None,
            "total_volume": _safe_int(df.iloc[14, 21]) if df.shape[1] > 21 else None,
        }

    # ========== 5日平均ボリューム ==========

    def _get_5d_avg_volume(self) -> Optional[float]:
        """jpx_put_call_ratio テーブルから直近5営業日の平均出来高を取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                rows = session.execute(text(
                    "SELECT call_volume, put_volume FROM jpx_put_call_ratio "
                    "WHERE product = 'nikkei225' AND (call_volume IS NOT NULL OR put_volume IS NOT NULL) "
                    "ORDER BY date DESC LIMIT 5"
                )).fetchall()
                if rows:
                    totals = [(r[0] or 0) + (r[1] or 0) for r in rows]
                    return round(sum(totals) / len(totals), 0)
        except Exception as e:
            logger.debug(f"[NK225Options] 5d avg volume query failed: {e}")
        return None

    # ========== 25D スキュー算出 ==========

    def _calculate_skew_metrics(
        self,
        strikes_list: List[Dict],
        atm_strike: int,
        underlying: float,
        dte: Optional[int],
        interest_rate: Optional[float],
    ) -> Dict[str, Optional[float]]:
        """
        25Dスキュー指標を算出

        25Dオプションのストライク近似 (Black-Scholes):
          フォワード F ≈ 原資産価格（配当無視、短期のため許容）
          σ = ATM IV (mid)
          T = DTE / 365

          25Dコールのストライク近似:
            K_25d_call = F * exp(+0.6745 * σ * √T - 0.5 * σ² * T)
          25Dプットのストライク近似:
            K_25d_put  = F * exp(-0.6745 * σ * √T - 0.5 * σ² * T)

          ここで 0.6745 = Φ^{-1}(0.75)（25Dコールの標準正規累積分布逆関数）

        戻り値:
          - skew_25d_put_iv: 25DプットのIV (%)
          - skew_25d_call_iv: 25DコールのIV (%)
          - skew_25d_rr: Risk Reversal = 25D Call IV - 25D Put IV
            （通常は負値 = プットスキュー = ダウンサイドプロテクション需要）
          - skew_25d_butterfly: (25D Call IV + 25D Put IV) / 2 - ATM IV
            （スマイルの曲率指標、通常は正値）
        """
        empty = {
            "skew_25d_put_iv": None,
            "skew_25d_call_iv": None,
            "skew_25d_rr": None,
            "skew_25d_butterfly": None,
        }

        if dte is None or dte <= 0 or not strikes_list:
            return empty

        # ATM IV mid を取得
        atm_data = None
        for s in strikes_list:
            if s["strike"] == atm_strike:
                atm_data = s
                break
        if atm_data is None:
            return empty

        atm_iv_call = atm_data.get("call_iv")
        atm_iv_put = atm_data.get("put_iv")
        if atm_iv_call is None and atm_iv_put is None:
            return empty

        atm_iv_mid = (
            ((atm_iv_call or 0) + (atm_iv_put or 0))
            / (2 if atm_iv_call and atm_iv_put else 1)
        )
        sigma = atm_iv_mid / 100.0  # decimal
        if sigma <= 0:
            return empty

        T = dte / 365.0
        vol_sqrt_t = sigma * math.sqrt(T)

        # 25D ストライク近似
        k_25d_call = underlying * math.exp(0.6745 * vol_sqrt_t - 0.5 * sigma ** 2 * T)
        k_25d_put = underlying * math.exp(-0.6745 * vol_sqrt_t - 0.5 * sigma ** 2 * T)

        # IVを線形補間
        iv_25d_call = _interpolate_iv(strikes_list, k_25d_call, "call_iv")
        iv_25d_put = _interpolate_iv(strikes_list, k_25d_put, "put_iv")

        if iv_25d_call is None or iv_25d_put is None:
            return empty

        rr = round(iv_25d_call - iv_25d_put, 2)
        butterfly = round((iv_25d_call + iv_25d_put) / 2 - atm_iv_mid, 2)

        return {
            "skew_25d_put_iv": round(iv_25d_put, 2),
            "skew_25d_call_iv": round(iv_25d_call, 2),
            "skew_25d_rr": rr,
            "skew_25d_butterfly": butterfly,
        }

    # ========== OIマージ ==========

    def _merge_oi_data(self, expiries_dict: Dict, oi_data: Dict) -> None:
        """OIデータを expiries_dict にin-placeマージ"""
        for cm, exp_info in expiries_dict.items():
            cm_short = cm[2:] if len(cm) == 6 else cm

            for strike, sd in exp_info["strikes_map"].items():
                put_key = (cm_short, strike, "P")
                call_key = (cm_short, strike, "C")

                if put_key in oi_data:
                    oi_entry = oi_data[put_key]
                    sd["put_oi"] = oi_entry.get("oi")
                    sd["put_volume"] = oi_entry.get("volume")
                    sd["oi_change_put"] = oi_entry.get("oi_change")
                    sd["prev_put_oi"] = oi_entry.get("prev_oi")

                if call_key in oi_data:
                    oi_entry = oi_data[call_key]
                    sd["call_oi"] = oi_entry.get("oi")
                    sd["call_volume"] = oi_entry.get("volume")
                    sd["oi_change_call"] = oi_entry.get("oi_change")
                    sd["prev_call_oi"] = oi_entry.get("prev_oi")

    # ========== 前日IVマージ ==========

    def _merge_prev_day_iv(
        self, expiries_dict: Dict, prev_expiries_dict: Optional[Dict]
    ) -> None:
        """前日IVデータをストライクレベルでマージ"""
        if not prev_expiries_dict:
            return

        for cm, exp_info in expiries_dict.items():
            prev_exp = prev_expiries_dict.get(cm)
            if not prev_exp:
                continue
            prev_strikes = prev_exp.get("strikes_map", {})

            for strike, sd in exp_info["strikes_map"].items():
                prev_sd = prev_strikes.get(strike)
                if prev_sd:
                    sd["prev_put_iv"] = prev_sd.get("put_iv")
                    sd["prev_call_iv"] = prev_sd.get("call_iv")

    # ========== 構造化 ==========

    def _build_expiries_list(
        self,
        expiries_dict: Dict,
        underlying_price: float,
        interest_rate: Optional[float],
        expiry_mapping: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        expiries_dict を構造化された expiries リストに変換

        ATM判定ロジック:
        1. 原資産価格（underlying_price）に最も近い行使価格をATMストライクとする
        2. ATM IV Mid = (ATM Call IV + ATM Put IV) / 2
        3. ATM Call/Put IVは当該ストライクの値を直接使用
        4. 当該ストライクにIV値がない場合、ATM IV Midのみnull
        """
        expiries = []

        for cm in sorted(expiries_dict.keys()):
            exp_info = expiries_dict[cm]
            strikes_map = exp_info["strikes_map"]

            if not strikes_map:
                continue

            # Expiry date and DTE from mapping or exp_info
            expiry_date = None
            dte = None
            if expiry_mapping and cm in expiry_mapping:
                expiry_date = expiry_mapping[cm]["expiry_date"]
                dte = expiry_mapping[cm]["dte"]
            elif "expiry_date" in exp_info:
                expiry_date = exp_info["expiry_date"]
                dte = exp_info.get("dte")

            if expiry_date is None:
                # Cannot determine expiry date, skip
                continue

            # ATM ± 40% filter (distant: ± 20%)
            dte_val = dte or 30
            pct_range = 0.20 if dte_val > 180 else 0.40
            lower_bound = underlying_price * (1 - pct_range)
            upper_bound = underlying_price * (1 + pct_range)

            filtered_strikes = []
            for s, sd in sorted(strikes_map.items()):
                if s < lower_bound or s > upper_bound:
                    has_data = (
                        (sd.get("put_settlement") and sd["put_settlement"] > 0)
                        or (sd.get("call_settlement") and sd["call_settlement"] > 0)
                        or (sd.get("put_oi") and sd["put_oi"] > 0)
                        or (sd.get("call_oi") and sd["call_oi"] > 0)
                    )
                    if not has_data:
                        continue
                filtered_strikes.append(sd)

            if not filtered_strikes:
                continue

            # ATM strike: nearest to underlying
            all_strike_vals = [sd["strike"] for sd in filtered_strikes]
            atm_strike = min(all_strike_vals, key=lambda s: abs(s - underlying_price))

            atm_data = strikes_map.get(atm_strike, {})
            atm_iv_call = atm_data.get("call_iv")
            atm_iv_put = atm_data.get("put_iv")
            atm_iv_mid = None
            if atm_iv_call is not None and atm_iv_put is not None:
                atm_iv_mid = round((atm_iv_call + atm_iv_put) / 2, 4)
            elif atm_iv_call is not None:
                atm_iv_mid = atm_iv_call
            elif atm_iv_put is not None:
                atm_iv_mid = atm_iv_put

            # Prev ATM IV mid
            prev_atm_iv_call = atm_data.get("prev_call_iv")
            prev_atm_iv_put = atm_data.get("prev_put_iv")
            prev_atm_iv_mid = None
            if prev_atm_iv_call is not None and prev_atm_iv_put is not None:
                prev_atm_iv_mid = round((prev_atm_iv_call + prev_atm_iv_put) / 2, 4)
            elif prev_atm_iv_call is not None:
                prev_atm_iv_mid = prev_atm_iv_call
            elif prev_atm_iv_put is not None:
                prev_atm_iv_mid = prev_atm_iv_put

            # Skew metrics
            skew = self._calculate_skew_metrics(
                filtered_strikes, atm_strike, underlying_price, dte, interest_rate
            )

            # Per-expiry OI/Volume aggregates
            total_call_oi = 0
            total_put_oi = 0
            prev_total_call_oi = 0
            prev_total_put_oi = 0
            total_call_volume = 0
            total_put_volume = 0
            for sd in filtered_strikes:
                total_call_oi += sd.get("call_oi") or 0
                total_put_oi += sd.get("put_oi") or 0
                prev_total_call_oi += sd.get("prev_call_oi") or 0
                prev_total_put_oi += sd.get("prev_put_oi") or 0
                total_call_volume += sd.get("call_volume") or 0
                total_put_volume += sd.get("put_volume") or 0

            expiries.append({
                "expiry": expiry_date,
                "contract_month": cm,
                "dte": dte,
                "atm_strike": atm_strike,
                "atm_iv_call": atm_iv_call,
                "atm_iv_put": atm_iv_put,
                "atm_iv_mid": atm_iv_mid,
                "prev_atm_iv_mid": prev_atm_iv_mid,
                **skew,
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
                "prev_total_call_oi": prev_total_call_oi,
                "prev_total_put_oi": prev_total_put_oi,
                "total_call_volume": total_call_volume,
                "total_put_volume": total_put_volume,
                "strikes": filtered_strikes,
            })

        return expiries

    # ========== 集計統計 ==========

    def _build_aggregate(
        self, expiries: List[Dict], market_vol: Optional[Dict]
    ) -> Dict:
        """全限月横断の集計統計を構築"""
        agg = {
            "total_call_oi": 0,
            "total_put_oi": 0,
            "prev_total_call_oi": 0,
            "prev_total_put_oi": 0,
            "total_call_volume": 0,
            "total_put_volume": 0,
            "volume_5d_avg": None,
        }

        for exp in expiries:
            agg["total_call_oi"] += exp.get("total_call_oi") or 0
            agg["total_put_oi"] += exp.get("total_put_oi") or 0
            agg["prev_total_call_oi"] += exp.get("prev_total_call_oi") or 0
            agg["prev_total_put_oi"] += exp.get("prev_total_put_oi") or 0
            agg["total_call_volume"] += exp.get("total_call_volume") or 0
            agg["total_put_volume"] += exp.get("total_put_volume") or 0

        # market_data_whole_day.xlsx のボリューム（より正確）
        if market_vol:
            agg["total_call_volume"] = market_vol.get("call_volume") or agg["total_call_volume"]
            agg["total_put_volume"] = market_vol.get("put_volume") or agg["total_put_volume"]

        agg["volume_5d_avg"] = self._get_5d_avg_volume()

        return agg

    # ========== ATM IV 履歴 ==========

    def _load_atm_iv_history(self) -> List[Dict]:
        try:
            data = redis_client.get(ATM_IV_HISTORY_KEY)
            if data and isinstance(data, list):
                return data
        except Exception:
            pass
        try:
            if ATM_IV_HISTORY_FILE.exists():
                with open(ATM_IV_HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _save_atm_iv_history(self, history: List[Dict]) -> None:
        try:
            redis_client.set(ATM_IV_HISTORY_KEY, history, expire=86400 * 400)
        except Exception as e:
            logger.debug(f"[NK225Options] Redis ATM IV history save error: {e}")
        try:
            with open(ATM_IV_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"[NK225Options] File ATM IV history save error: {e}")

    def _update_atm_iv_history(
        self, expiries: List[Dict], data_date: str, underlying_price: float
    ) -> List[Dict]:
        history = self._load_atm_iv_history()

        if len(data_date) == 8 and "-" not in data_date:
            formatted_date = f"{data_date[:4]}-{data_date[4:6]}-{data_date[6:8]}"
        else:
            formatted_date = data_date

        history = [h for h in history if h["date"] != formatted_date]

        for exp in expiries:
            if exp.get("atm_iv_mid") is not None:
                history.append({
                    "date": formatted_date,
                    "expiry": exp["expiry"],
                    "contract_month": exp["contract_month"],
                    "dte": exp.get("dte"),
                    "atm_iv_mid": exp["atm_iv_mid"],
                    "atm_iv_call": exp.get("atm_iv_call"),
                    "atm_iv_put": exp.get("atm_iv_put"),
                    "underlying": underlying_price,
                })

        cutoff = (datetime.now(JST) - timedelta(days=365)).strftime("%Y-%m-%d")
        history = [h for h in history if h["date"] >= cutoff]
        history.sort(key=lambda h: (h["date"], h["expiry"]))

        self._save_atm_iv_history(history)
        return history

    # ========== メインビルド ==========

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """全データを構築（ローカルファイル優先 → URLフォールバック）"""

        # ローカルファイル探索
        local_dates = self._discover_local_dates()

        if local_dates:
            result = self._build_from_local(local_dates)
            if result:
                return result
            logger.info("[NK225Options] Local build failed, falling back to URL fetch")

        return self._build_from_url()

    def _build_from_local(
        self, local_dates: List[Tuple[str, Dict[str, Optional[Path]]]]
    ) -> Optional[Dict[str, Any]]:
        """ローカルファイルから2日分のデータを構築"""

        today_date, today_files = local_dates[0]
        prev_date = None
        prev_files = None
        if len(local_dates) >= 2:
            prev_date, prev_files = local_dates[1]

        # === 当日データ ===
        underlying_price = None
        interest_rate = None
        expiries_dict = None
        expiry_mapping = None

        # Priority 1: ose*tp.csv (fall back to nearest date if missing)
        ose_tp_file = today_files.get("ose_tp")
        if not ose_tp_file:
            for _, other_files in local_dates[1:]:
                if other_files.get("ose_tp"):
                    ose_tp_file = other_files["ose_tp"]
                    logger.info(f"[NK225Options] ose_tp fallback: using {ose_tp_file.name}")
                    break
        if ose_tp_file:
            parsed = self._parse_ose_tp_csv(ose_tp_file)
            if parsed:
                underlying_price = parsed["underlying_price"]
                interest_rate = parsed["interest_rate"]
                expiries_dict = parsed["expiries_dict"]

        # Priority 2: rb.csv (for expiry/DTE, or as fallback)
        if today_files.get("rb"):
            expiry_mapping = self._extract_expiry_mapping(today_files["rb"])

            if expiries_dict is None:
                # Fallback: use rb.csv for full data
                rb_parsed = self._parse_rb_csv_full(today_files["rb"])
                if rb_parsed:
                    underlying_price = rb_parsed["underlying_price"]
                    interest_rate = rb_parsed.get("interest_rate")
                    expiries_dict = rb_parsed["expiries_dict"]
                    # rb.csv already has expiry_date in expiries_dict
                    expiry_mapping = None
            else:
                # ose_tp may be from an older date; use rb.csv's underlying
                # price since rb is always the latest date slot
                rb_underlying = self._extract_underlying_from_rb(today_files["rb"])
                if rb_underlying:
                    underlying_price = rb_underlying

        if expiries_dict is None or underlying_price is None:
            return None

        # Priority 3: OI data
        # JPX OI files use previous business day's date, so the OI file
        # for today's settlement may be in an earlier date slot.
        oi_file = today_files.get("oi")
        if not oi_file:
            for _, other_files in local_dates[1:]:
                if other_files.get("oi"):
                    oi_file = other_files["oi"]
                    logger.info(f"[NK225Options] OI fallback: using {oi_file.name}")
                    break
        if oi_file:
            oi_data = self._parse_oi_local(oi_file)
            if oi_data:
                self._merge_oi_data(expiries_dict, oi_data)

        # Priority 4: Market data volume
        market_vol = None
        md_file = today_files.get("market_data")
        if not md_file:
            for _, other_files in local_dates[1:]:
                if other_files.get("market_data"):
                    md_file = other_files["market_data"]
                    logger.info(f"[NK225Options] Market data fallback: using {md_file.name}")
                    break
        if md_file:
            market_vol = self._parse_market_data_volume(md_file)

        # === 前日データ (IVのみ) ===
        prev_underlying_price = None
        if prev_files:
            prev_expiries_dict = None
            if prev_files.get("ose_tp"):
                prev_parsed = self._parse_ose_tp_csv(prev_files["ose_tp"])
                if prev_parsed:
                    prev_underlying_price = prev_parsed["underlying_price"]
                    prev_expiries_dict = prev_parsed["expiries_dict"]
            elif prev_files.get("rb"):
                prev_rb = self._parse_rb_csv_full(prev_files["rb"])
                if prev_rb:
                    prev_underlying_price = prev_rb["underlying_price"]
                    prev_expiries_dict = prev_rb["expiries_dict"]

            if prev_expiries_dict:
                self._merge_prev_day_iv(expiries_dict, prev_expiries_dict)

        # === 構造化 ===
        expiries = self._build_expiries_list(
            expiries_dict, underlying_price, interest_rate, expiry_mapping
        )

        if not expiries:
            return None

        # 前日スキューも算出
        prev_skew_data = {}
        if prev_files and prev_underlying_price:
            prev_expiries_dict_for_skew = None
            if prev_files.get("ose_tp"):
                p = self._parse_ose_tp_csv(prev_files["ose_tp"])
                if p:
                    prev_expiries_dict_for_skew = p["expiries_dict"]
            if prev_expiries_dict_for_skew:
                for cm, exp_info in prev_expiries_dict_for_skew.items():
                    sm = exp_info["strikes_map"]
                    strikes_list = sorted(sm.values(), key=lambda x: x["strike"])
                    if not strikes_list:
                        continue
                    atm = min(strikes_list, key=lambda x: abs(x["strike"] - prev_underlying_price))["strike"]
                    skew = self._calculate_skew_metrics(
                        strikes_list, atm, prev_underlying_price,
                        None, None  # dte and rate not critical for prev day
                    )
                    prev_skew_data[cm] = skew

        # Add prev_skew_25d_rr to expiries
        for exp in expiries:
            cm = exp["contract_month"]
            if cm in prev_skew_data:
                exp["prev_skew_25d_rr"] = prev_skew_data[cm].get("skew_25d_rr")
            else:
                exp.setdefault("prev_skew_25d_rr", None)

        # Aggregate
        aggregate = self._build_aggregate(expiries, market_vol)

        # ATM IV history
        atm_iv_history = self._update_atm_iv_history(
            expiries, today_date, underlying_price
        )

        # Format dates
        formatted_date = f"{today_date[:4]}-{today_date[4:6]}-{today_date[6:8]}"
        formatted_prev = None
        if prev_date:
            formatted_prev = f"{prev_date[:4]}-{prev_date[4:6]}-{prev_date[6:8]}"

        nearest = expiries[0] if expiries else None
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[NK225Options] Local build: date={formatted_date}, "
            f"prev_date={formatted_prev}, "
            f"underlying={underlying_price:.0f}, "
            f"expiries={len(expiries)}"
        )

        return {
            "data": {
                "underlying_price": underlying_price,
                "prev_underlying_price": prev_underlying_price,
                "date": formatted_date,
                "prev_date": formatted_prev,
                "expiries": expiries,
                "atm_iv_history": atm_iv_history,
                "aggregate": aggregate,
            },
            "latest": {
                "date": formatted_date,
                "underlying_price": underlying_price,
                "nearest_expiry": nearest["expiry"] if nearest else None,
                "nearest_dte": nearest.get("dte") if nearest else None,
                "atm_iv_mid": nearest.get("atm_iv_mid") if nearest else None,
                "atm_iv_call": nearest.get("atm_iv_call") if nearest else None,
                "atm_iv_put": nearest.get("atm_iv_put") if nearest else None,
            },
            "metadata": {
                "source": "JPX (Local Files)",
                "expiry_count": len(expiries),
                "total_strikes": sum(len(e["strikes"]) for e in expiries),
                "history_days": len(set(h["date"] for h in atm_iv_history)),
                "has_prev_day": prev_date is not None,
            },
            "cached": False,
            "source": "local",
            "last_updated": now_str,
        }

    def _build_from_url(self) -> Optional[Dict[str, Any]]:
        """URLからデータを取得（ローカルファイルがない場合のフォールバック）"""
        import requests
        import pandas as pd

        # Settlement CSV取得
        today = datetime.now(JST).date()
        csv_result = None

        for i in range(10):
            d = today - timedelta(days=i)
            if d.weekday() >= 5:
                continue
            date_str = d.strftime("%Y%m%d")
            url = SETTLEMENT_CSV_URL.format(date=date_str)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 500:
                    try:
                        df = pd.read_csv(
                            io.BytesIO(resp.content),
                            encoding="shift_jis",
                            skiprows=2,
                        )
                    except UnicodeDecodeError:
                        df = pd.read_csv(
                            io.BytesIO(resp.content),
                            encoding="cp932",
                            skiprows=2,
                        )

                    if df.empty or len(df.columns) < 12:
                        continue

                    df.columns = [c.strip() for c in df.columns]
                    issue_col = df.columns[1]
                    mask = df[issue_col].astype(str).str.contains(
                        "PUT_225_|CAL_225_", regex=True, na=False
                    )
                    nk225_df = df[mask].copy()
                    if not nk225_df.empty:
                        csv_result = (nk225_df, date_str)
                        break
            except Exception:
                continue

        if csv_result is None:
            return None

        nk225_df, data_date = csv_result

        # Parse using rb.csv full parser logic
        col_issue_name = nk225_df.columns[1]
        col_contract_month = nk225_df.columns[3]
        col_strike = nk225_df.columns[4]
        col_settlement = nk225_df.columns[5]
        col_theoretical = nk225_df.columns[6]
        col_underlying_price = nk225_df.columns[7]
        col_iv = nk225_df.columns[8]
        col_dte = nk225_df.columns[10]

        underlying_price = None
        vals = nk225_df[col_underlying_price].dropna()
        if len(vals) > 0:
            underlying_price = _safe_float(vals.iloc[0])
        if underlying_price is None or underlying_price <= 0:
            return None

        expiries_dict: Dict[str, Dict] = {}

        for _, row in nk225_df.iterrows():
            issue_name = str(row.get(col_issue_name, "")).strip()
            m = ISSUE_NAME_RE.match(issue_name)
            if not m:
                continue

            pc_type = m.group(1)
            expiry_yymmdd = m.group(2)
            strike = int(m.group(3))
            contract_month = str(row.get(col_contract_month, "")).strip()

            try:
                yy = int(expiry_yymmdd[:2])
                mm_exp = int(expiry_yymmdd[2:4])
                dd_exp = int(expiry_yymmdd[4:6])
                expiry_date = f"20{yy:02d}-{mm_exp:02d}-{dd_exp:02d}"
            except (ValueError, IndexError):
                continue

            settlement = _safe_float(row.get(col_settlement))
            theoretical = _safe_float(row.get(col_theoretical))
            iv = _filter_iv(_safe_float(row.get(col_iv)))
            dte = _safe_int(row.get(col_dte))

            if contract_month not in expiries_dict:
                expiries_dict[contract_month] = {
                    "expiry_date": expiry_date,
                    "dte": dte,
                    "strikes_map": {},
                }

            sd = expiries_dict[contract_month]["strikes_map"].setdefault(
                strike, {
                    "strike": strike,
                    "put_settlement": None, "put_theoretical": None, "put_iv": None,
                    "call_settlement": None, "call_theoretical": None, "call_iv": None,
                    "put_oi": None, "call_oi": None,
                    "put_volume": None, "call_volume": None,
                    "prev_put_iv": None, "prev_call_iv": None,
                    "prev_put_oi": None, "prev_call_oi": None,
                    "oi_change_put": None, "oi_change_call": None,
                    "quality": _quality_flag(strike, underlying_price),
                }
            )

            if pc_type == "PUT":
                sd["put_settlement"] = settlement
                sd["put_theoretical"] = theoretical
                sd["put_iv"] = iv
            else:
                sd["call_settlement"] = settlement
                sd["call_theoretical"] = theoretical
                sd["call_iv"] = iv

        # OI from URL
        oi_data = self._fetch_open_interest_url(data_date)
        if oi_data:
            self._merge_oi_data(expiries_dict, oi_data)

        # Build expiries list
        expiries = self._build_expiries_list(expiries_dict, underlying_price, None)

        if not expiries:
            return None

        # Add prev_skew_25d_rr as None for URL-fetched data
        for exp in expiries:
            exp.setdefault("prev_skew_25d_rr", None)

        aggregate = self._build_aggregate(expiries, None)
        atm_iv_history = self._update_atm_iv_history(
            expiries, data_date, underlying_price
        )

        formatted_date = f"{data_date[:4]}-{data_date[4:6]}-{data_date[6:8]}"
        nearest = expiries[0] if expiries else None
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[NK225Options] URL build: date={formatted_date}, "
            f"underlying={underlying_price:.0f}, "
            f"expiries={len(expiries)}"
        )

        return {
            "data": {
                "underlying_price": underlying_price,
                "prev_underlying_price": None,
                "date": formatted_date,
                "prev_date": None,
                "expiries": expiries,
                "atm_iv_history": atm_iv_history,
                "aggregate": aggregate,
            },
            "latest": {
                "date": formatted_date,
                "underlying_price": underlying_price,
                "nearest_expiry": nearest["expiry"] if nearest else None,
                "nearest_dte": nearest.get("dte") if nearest else None,
                "atm_iv_mid": nearest.get("atm_iv_mid") if nearest else None,
                "atm_iv_call": nearest.get("atm_iv_call") if nearest else None,
                "atm_iv_put": nearest.get("atm_iv_put") if nearest else None,
            },
            "metadata": {
                "source": "JPX (URL Fetch)",
                "expiry_count": len(expiries),
                "total_strikes": sum(len(e["strikes"]) for e in expiries),
                "history_days": len(set(h["date"] for h in atm_iv_history)),
                "has_prev_day": False,
            },
            "cached": False,
            "source": "api",
            "last_updated": now_str,
        }

    def _fetch_open_interest_url(self, data_date_str: str) -> Optional[Dict]:
        """Open Interest XLSX をURLからダウンロード"""
        import requests
        import pandas as pd

        try:
            data_date = datetime.strptime(data_date_str, "%Y%m%d").date()
        except ValueError:
            return None

        dates_to_try = [data_date]
        prev = _prev_business_day(data_date)
        dates_to_try.append(prev)
        prev2 = _prev_business_day(prev)
        dates_to_try.append(prev2)

        for d in dates_to_try:
            ds = d.strftime("%Y%m%d")
            url = OPEN_INTEREST_URL.format(date=ds)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                if resp.status_code != 200 or len(resp.content) < 1000:
                    continue

                df = pd.read_excel(
                    io.BytesIO(resp.content),
                    sheet_name=1,
                    header=None,
                    engine="openpyxl",
                )

                result: Dict[tuple, Dict] = {}
                put_call_cols = [
                    (0, 1, 2, 3, 4),
                    (6, 7, 8, 9, 10),
                ]

                for idx in range(df.shape[0]):
                    for name_col, vol_col, oi_col, change_col, prev_oi_col in put_call_cols:
                        if name_col >= df.shape[1]:
                            continue
                        cell_val = str(df.iloc[idx, name_col]).strip()
                        m = OI_ISSUE_RE.search(cell_val)
                        if m:
                            pc = m.group(1)
                            contract_month = m.group(2)
                            strike = int(m.group(3))

                            volume = _safe_int(df.iloc[idx, vol_col]) if vol_col < df.shape[1] else None
                            oi = _safe_int(df.iloc[idx, oi_col]) if oi_col < df.shape[1] else None
                            oi_change = _safe_int(df.iloc[idx, change_col]) if change_col < df.shape[1] else None
                            prev_oi = _safe_int(df.iloc[idx, prev_oi_col]) if prev_oi_col < df.shape[1] else None

                            key = (contract_month, strike, pc)
                            result[key] = {
                                "oi": oi,
                                "volume": volume,
                                "oi_change": oi_change,
                                "prev_oi": prev_oi,
                            }

                if result:
                    logger.info(f"[NK225Options] OI data fetched from URL: {ds} ({len(result)} entries)")
                    return result

            except Exception as e:
                logger.debug(f"[NK225Options] OI URL fetch failed for {ds}: {e}")
                continue

        return None

    # ========== キャッシュ ==========

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(SNAPSHOT_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NK225Options] Redis save error: {e}")
        try:
            with open(SNAPSHOT_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"[NK225Options] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(SNAPSHOT_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NK225Options] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if SNAPSHOT_CACHE_FILE.exists():
                with open(SNAPSHOT_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[NK225Options] File load error: {e}")
        return None


# シングルトン
nikkei225_options_service = Nikkei225OptionsService()
