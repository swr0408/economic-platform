# -*- coding: utf-8 -*-
"""
Phase 2: 相関・先行/遅行 解析エンジン。

定常化 (価格=対数差分 / レート=差分 / 利回り=bp差分) した上で:
  - ラグ別相互相関 (numpy ベクトル化, 共通月次グリッド上)
  - Granger 因果 (定常化系列)
  - 同時点相関
  - Benjamini-Hochberg FDR 補正
  - シーズナリティ月別プロファイル相関

幻覚 (偽相関) 回避: 全系列を差分化して定常化 → トレンド由来の見せかけ相関を除去。
ペアワイズ完全重複に最小 n を課し、p 値を併記、候補集合横断で FDR。
"""
import warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

_YIELD_KEYS = ("us02y", "us10y", "us30y", "_yield", "bank_rate", "policy_rate",
               "repo_rate", "bond", "10y", "2y", "30y", "boe_bank_rate")


class Engine:
    """long_df / cat_df を受け取り、月次・四半期パネルを内部生成して解析する。"""

    def __init__(self, long_df: pd.DataFrame, cat_df: pd.DataFrame):
        self.long = long_df.copy()
        self.long["date"] = pd.to_datetime(self.long["date"])
        self.cat = cat_df.set_index("series_id")
        self._raw_cache = {}
        self._monthly = {}        # transformed monthly Series
        self._monthly_lvl = {}    # raw monthly level
        self._quarterly = {}
        self._aligned = {}        # transformed monthly on GLOBAL grid (np.array)
        # group long by series for O(1) access
        self._groups = {sid: g for sid, g in self.long.groupby("series_id")}
        # global monthly grid
        mn, mx = self.long["date"].min(), self.long["date"].max()
        self.grid = pd.date_range(mn.to_period("M").to_timestamp(),
                                  mx.to_period("M").to_timestamp(), freq="MS")
        self._gridpos = {ts: i for i, ts in enumerate(self.grid)}

    # ---- transforms ----
    @staticmethod
    def _is_yield_like(series_id):
        s = (series_id or "").lower()
        return any(k in s for k in _YIELD_KEYS)

    @staticmethod
    def _auto_transform(s, force_diff=False):
        s = s.dropna()
        if len(s) < 6:
            return s.diff().dropna()
        if force_diff:
            return s.diff().dropna()
        pos = (s > 0).all()
        rng = (s.max() / s.min()) if (pos and s.min() > 0) else np.inf
        if pos and rng > 4:
            return np.log(s).diff().dropna()
        return s.diff().dropna()

    def _raw(self, sid):
        g = self._groups.get(sid)
        if g is None:
            return pd.Series(dtype=float)
        return pd.Series(g["value"].values, index=g["date"].values).sort_index()

    def monthly_level(self, sid):
        if sid in self._monthly_lvl:
            return self._monthly_lvl[sid]
        s = self._raw(sid)
        m = s.resample("MS").last().dropna() if not s.empty else s
        self._monthly_lvl[sid] = m
        return m

    def monthly(self, sid):
        if sid in self._monthly:
            return self._monthly[sid]
        t = self._auto_transform(self.monthly_level(sid), force_diff=self._is_yield_like(sid))
        self._monthly[sid] = t
        return t

    def quarterly(self, sid):
        if sid in self._quarterly:
            return self._quarterly[sid]
        s = self._raw(sid)
        q = s.resample("QS").last().dropna() if not s.empty else s
        t = self._auto_transform(q, force_diff=self._is_yield_like(sid))
        self._quarterly[sid] = t
        return t

    def _aligned_monthly(self, sid):
        """transformed monthly を GLOBAL grid 上の np.array (NaN 埋め) で返す (キャッシュ)。"""
        if sid in self._aligned:
            return self._aligned[sid]
        t = self.monthly(sid)
        arr = np.full(len(self.grid), np.nan)
        for ts, v in t.items():
            tsm = pd.Timestamp(ts).to_period("M").to_timestamp()
            i = self._gridpos.get(tsm)
            if i is not None:
                arr[i] = v
        self._aligned[sid] = arr
        return arr

    # ---- lagged cross-correlation ----
    def lagcorr(self, target_id, cand_id, freq="M", maxlag=12, minn=24):
        """
        corr(target_t, cand_{t-k}), k in [-maxlag, maxlag].
        k>0 => cand LEADS target. ベストラグ (|corr|最大) を返す。
        """
        if freq == "Q":
            return self._lagcorr_pd(target_id, cand_id, maxlag, minn)
        a = self._aligned_monthly(target_id)
        b = self._aligned_monthly(cand_id)
        n = len(a)
        best = None
        for k in range(-maxlag, maxlag + 1):
            # cand shifted by k: pair (a[i], b[i-k])
            if k >= 0:
                aa, bb = a[k:], b[: n - k] if k > 0 else b
            else:
                aa, bb = a[: n + k], b[-k:]
            mask = ~np.isnan(aa) & ~np.isnan(bb)
            m = int(mask.sum())
            if m < minn:
                continue
            x, y = aa[mask], bb[mask]
            if x.std() == 0 or y.std() == 0:
                continue
            r = float(np.corrcoef(x, y)[0, 1])
            if np.isnan(r):
                continue
            if best is None or abs(r) > abs(best["corr"]):
                # p-value (two-sided) from r and m
                p = self._pval(r, m)
                best = {"lag": k, "corr": r, "p": p, "n": m}
        if best is None:
            return None
        # contemporaneous
        mask0 = ~np.isnan(a) & ~np.isnan(b)
        if int(mask0.sum()) >= minn:
            x0, y0 = a[mask0], b[mask0]
            if x0.std() > 0 and y0.std() > 0:
                r0 = float(np.corrcoef(x0, y0)[0, 1])
                best["corr_lag0"] = r0
                best["n_lag0"] = int(mask0.sum())
        return best

    @staticmethod
    def _pval(r, n):
        if n < 4 or abs(r) >= 1.0:
            return 0.0
        t = r * np.sqrt((n - 2) / (1 - r * r))
        return float(2 * stats.t.sf(abs(t), n - 2))

    def _lagcorr_pd(self, target_id, cand_id, maxlag, minn):
        t = self.quarterly(target_id)
        x = self.quarterly(cand_id)
        if t.empty or x.empty:
            return None
        df = pd.concat([t.rename("t"), x.rename("x")], axis=1)
        best = None
        for k in range(-maxlag, maxlag + 1):
            pair = pd.concat([df["t"], df["x"].shift(k)], axis=1).dropna()
            if len(pair) < minn:
                continue
            if pair.iloc[:, 0].std() == 0 or pair.iloc[:, 1].std() == 0:
                continue
            r, p = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
            if np.isnan(r):
                continue
            if best is None or abs(r) > abs(best["corr"]):
                best = {"lag": k, "corr": r, "p": p, "n": len(pair)}
        if best is None:
            return None
        pair0 = df.dropna()
        if len(pair0) >= minn and pair0["t"].std() > 0 and pair0["x"].std() > 0:
            r0, _ = stats.pearsonr(pair0["t"], pair0["x"])
            best["corr_lag0"] = r0
            best["n_lag0"] = len(pair0)
        return best

    def granger_pair(self, target_id, cand_id, freq="M", maxlag=6, minn=40):
        """lags 1..maxlag で cand -> target (cand が target 予測に寄与) の最小 p 値。"""
        from statsmodels.tsa.stattools import grangercausalitytests
        t = self.quarterly(target_id) if freq == "Q" else self.monthly(target_id)
        x = self.quarterly(cand_id) if freq == "Q" else self.monthly(cand_id)
        df = pd.concat([t.rename("t"), x.rename("x")], axis=1).dropna()
        if len(df) < minn or df["t"].std() == 0 or df["x"].std() == 0:
            return None
        try:
            res = grangercausalitytests(df[["t", "x"]], maxlag=maxlag, verbose=False)
        except Exception:
            return None
        best_p, best_lag = 1.0, None
        for lag, r in res.items():
            p = r[0]["ssr_ftest"][1]
            if p < best_p:
                best_p, best_lag = p, lag
        return {"p": best_p, "lag": best_lag, "n": len(df)}

    # ---- seasonality month-of-year profile ----
    def seasonal_profile(self, sid):
        m = self.monthly_level(sid)
        if len(m) < 24:
            return None
        if (m > 0).all() and m.min() > 0:
            chg = np.log(m).diff().dropna()
        else:
            chg = m.diff().dropna()
        prof = chg.groupby(chg.index.month).mean().reindex(range(1, 13))
        if prof.isna().any():
            return None
        return prof.values

    def seasonal_profile_corr(self, target_id, cand_id):
        a = self.seasonal_profile(target_id)
        b = self.seasonal_profile(cand_id)
        if a is None or b is None:
            return None
        r, p = stats.pearsonr(a, b)
        return {"corr": r, "p": p}


def bh_fdr(pvals, alpha=0.05):
    """Benjamini-Hochberg。入力順に揃えた採択 bool 配列を返す。"""
    p = np.asarray(pvals, float)
    n = len(p)
    if n == 0:
        return np.zeros(0, bool)
    order = np.argsort(p)
    ranked = p[order]
    thresh = alpha * (np.arange(1, n + 1) / n)
    passed = ranked <= thresh
    rej = np.zeros(n, bool)
    if passed.any():
        kmax = np.max(np.where(passed)[0])
        rej_sorted = np.zeros(n, bool)
        rej_sorted[: kmax + 1] = True
        rej[order] = rej_sorted
    return rej
