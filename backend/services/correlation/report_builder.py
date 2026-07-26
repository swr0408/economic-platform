# -*- coding: utf-8 -*-
"""
Phase 3: 成果物ビルダー。

clean 候補 (全1,355系列クラス) に対し、各国主要指標と主要銘柄をターゲットとして
相関/先行性を計算し、master 限定レポートの成果物を出力する:

  <as_of>/manifest.json
  <as_of>/sections/*.md
  <as_of>/matrices/*.csv
  <as_of>/catalog.csv
"""
import json
import shutil

import numpy as np
import pandas as pd

import html as _html

from .paths import as_of_dir, latest_pointer, REPORTS_ROOT
from . import loader, registry, labels
from .engine import Engine, bh_fdr

ROBUST_MIN_N = 60
ROBUST_MIN_CORR = 0.30
ROBUST_GRANGER_P = 0.05

# 高確度先行 (厳格フィルタ): robust より更に絞り、見せかけ (単一レジーム/合わせ込み/長ラグ過学習) を排除
HC_MIN_N = 120          # 複数の景気循環をまたぐ (単一レジーム artifact を排除)
HC_MIN_CORR = 0.40
HC_MAX_LAG = 6          # 過学習しやすい長ラグ先行を排除
HC_GRANGER_P = 0.01     # より厳しい予測的因果
HC_LAG0_CONTRA = 0.15   # 同時相関がこの強さで逆符号なら合わせ込み疑い→排除


# ---------------- helpers ----------------
def _clean_ids(cat: pd.DataFrame):
    c = cat["series_id"].str.lower()
    mask = (
        ~c.str.startswith("macro/earnings")
        & ~c.str.contains("forecast|scenario|fan|auction_size|refunding", regex=True)
        & ~c.str.contains(r"/test_response|/test_unemp|/test_", regex=True)  # テスト用ジャンク系列を除外
        & ~c.str.contains(r"nairu/data::unrate", regex=True)  # NAIRUキャッシュ内の失業率オーバーレイ複製を除外(本物NAIRUは残す)
        & (cat["n"] >= 24)
    )
    return list(cat[mask]["series_id"])


def _label(cat_idx, sid):
    """series_id → 和訳の読みやすいラベル。"""
    return labels.readable(sid, cat_idx)


def _corr_bg(r):
    """相関値→セル背景色 (正=緑/負=赤、濃さ=|r|)。逆相関も色で判別可。"""
    try:
        r = float(r)
    except (TypeError, ValueError):
        return ""
    a = min(0.60, abs(r) * 0.7)
    if a < 0.08:
        return ""
    rgb = "16,185,129" if r >= 0 else "239,68,68"
    return f"background:rgba({rgb},{a:.2f})"


def _fmt(v):
    if isinstance(v, float):
        if v != v:  # NaN
            return ""
        return f"{v:.3f}" if abs(v) < 1000 else f"{v:.0f}"
    return _html.escape(str(v))


def _html_table(df, cols, headers, corr_col="corr"):
    """データ表を HTML で生成。相関セルを色付け、robust 先行行を強調。

    rehypeRaw 前提。生成元は信頼できるバッチ出力でユーザー入力は流入しない。
    """
    ths = "".join(f"<th>{_html.escape(h)}</th>" for h in headers)
    body = []
    for _, r in df.iterrows():
        robust = bool(r.get("robust_lead", False))
        best_lag = r.get("best_lag", 0)
        tds = []
        for col in cols:
            v = r.get(col, "")
            style = ""
            if col == corr_col:
                bg = _corr_bg(v)
                style = f' style="{bg};text-align:right"' if bg else ' style="text-align:right"'
                v = f"{float(v):+.3f}" if isinstance(v, (int, float)) and v == v else _fmt(v)
            elif col == "lead_lag":
                # 先行性の強調: robust=濃, 単なる先行=淡
                if robust:
                    style = ' style="background:rgba(59,130,246,0.40);font-weight:600"'
                elif isinstance(best_lag, (int, float)) and best_lag >= 1:
                    style = ' style="background:rgba(59,130,246,0.15)"'
                v = _fmt(v)
            else:
                v = _fmt(v)
            tds.append(f"<td{style}>{v}</td>")
        tr_style = ' style="font-weight:600"' if robust else ""
        body.append(f"<tr{tr_style}>" + "".join(tds) + "</tr>")
    return (f'<table class="corr-tbl"><thead><tr>{ths}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def _lead_lag_text(k):
    if k > 0:
        return f"先行{k}ヶ月"
    if k < 0:
        return f"遅行{-k}ヶ月"
    return "同時"


def rank_target(eng: Engine, cat_idx, target_id, candidate_ids, freq="M",
                maxlag=12, minn=24):
    rows = []
    for cid in candidate_ids:
        if cid == target_id:
            continue
        lc = eng.lagcorr(target_id, cid, freq=freq, maxlag=maxlag, minn=minn)
        if lc is None:
            continue
        # 別IDだが値が実質同一の"自己重複"系列を除外(差分系列で同時|r|≈1.0は同一系列のみ)。
        # 例: nairu/data::unrate が失業率ターゲットと r=1.000/Granger p=1.000 で上位を汚す。
        _l0 = lc.get("corr_lag0")
        if abs(lc["corr"]) >= 0.9999 and _l0 is not None and abs(_l0) >= 0.9999:
            continue
        rows.append({
            "candidate": cid, "label": _label(cat_idx, cid),
            "best_lag": lc["lag"], "corr": round(lc["corr"], 3),
            "p": lc["p"], "n": lc["n"],
            "corr_lag0": round(lc.get("corr_lag0", np.nan), 3),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["fdr_sig"] = bh_fdr(df["p"].values, alpha=0.05)
    # Granger on prefilter (significant, non-trivial, enough overlap)
    pre = df[(df.fdr_sig) & (df["corr"].abs() >= 0.3) & (df["n"] >= 48)]["candidate"].tolist()
    gp = {}
    for cid in pre:
        g = eng.granger_pair(target_id, cid, freq=freq, maxlag=6)
        gp[cid] = round(g["p"], 4) if g else np.nan
    df["granger_p"] = df["candidate"].map(gp)
    df["lead_lag"] = df["best_lag"].map(_lead_lag_text)
    df["robust_lead"] = (
        (df["best_lag"] >= 1) & (df["best_lag"] <= 12)
        & (df["n"] >= ROBUST_MIN_N) & (df["corr"].abs() >= ROBUST_MIN_CORR)
        & (df["granger_p"] < ROBUST_GRANGER_P)
    )
    # 高確度先行: robust の部分集合。同時相関の符号整合 + 長サンプル + 短ラグ + 厳しい Granger。
    l0 = df["corr_lag0"]
    sign_contra = (np.sign(df["corr"]) != np.sign(l0)) & (l0.abs() >= HC_LAG0_CONTRA)
    df["high_conf"] = (
        (df["best_lag"] >= 1) & (df["best_lag"] <= HC_MAX_LAG)
        & (df["n"] >= HC_MIN_N) & (df["corr"].abs() >= HC_MIN_CORR)
        & (df["granger_p"] < HC_GRANGER_P)
        & l0.notna() & (~sign_contra)
    )
    df["abscorr"] = df["corr"].abs()
    df = df.sort_values("abscorr", ascending=False).drop(columns="abscorr").reset_index(drop=True)
    return df


# ---------------- section renderers ----------------
def _overview_md(meta):
    cov = meta["data_coverage"]
    return f"""# 相関・先行性レポート — 概要と読み方

**as-of: {meta['as_of']}** / 生成日時: {meta['generated_at']}
データ範囲: {cov['start']} 〜 {cov['end']} / 解析対象系列: {meta['n_clean']:,}（全{meta['n_series']:,}系列中、決算・予測系列を除外）

## このレポートの目的
各国の主要経済指標（CPI・政策金利・雇用者数・失業率・GDP・小売）および主要銘柄に対し、
**何が先行し、何と相関するか**をローカル実データのみから計算したものです。

## 手法
- 全系列を月次（GDP等は四半期）へ整列し、**定常化**（価格=対数差分／レート=差分／利回り=bp差分）。
  → トレンド由来の見せかけ相関を除去。
- **ラグ別相互相関**（±12期）でベストラグを検出（k>0=候補が先行）。
- **Granger 因果**で予測的因果を検定。
- 候補集合横断で **FDR（Benjamini-Hochberg）補正**。

## 信頼度の読み方（重要・3層）
- **上位の相関**: FDR有意な co-movement。同時/先行/遅行が混在。「何と動くか」の俯瞰用。
- **robust 先行**: 一応「先行」を主張する層。`n≥{ROBUST_MIN_N} ∧ |r|≥{ROBUST_MIN_CORR} ∧ Granger p<{ROBUST_GRANGER_P}`。ただし**単一レジーム(短n)・合わせ込み(同時相関が逆符号)・長ラグ過学習が混入**するので鵜呑み厳禁。
- **高確度先行（厳格）**: 見せかけを排除した優位性の高い層のみ。`n≥{HC_MIN_N}(複数の景気循環をまたぐ) ∧ |r|≥{HC_MIN_CORR} ∧ 先行1〜{HC_MAX_LAG}ヶ月 ∧ Granger p<{HC_GRANGER_P} ∧ 同時相関と符号整合`。**実用の先行指標はまずここを見る**。
- **見せかけ(spurious)の見分け方**: ①**n が小さい**(単一レジーム。例: コロナ期のみ n≈70)②**同時相関(lag0)がベストラグと逆符号**(合わせ込み)③**長い先行ラグ×小n**(過学習)④**外国政策金利や世界系がクラスタで並ぶ**(共通の世界的景気サイクルの指紋で独立シグナルでない)。これらは「共通要因での連動」を示すに留まり、**予測には使えない**。

## 限界（必読）
- **相関は因果ではない**。Granger は予測的因果の必要条件にすぎない。
- 関係は**レジーム依存**（低金利期と利上げ期で先行関係は変わる）。本レポートは {meta['as_of']} 時点のスナップショット。
- 速報/改定・発表ラグ・タイムゾーン差は点合わせ誤差を生む。
- 政策金利が無い国・概念は解決できず欠落する場合がある（米は2年債利回りで金利パスを代理）。

## ダウンロード
フル結果（全ペアのマトリクス・全ターゲットのランキング）はページ下部のCSVリンクから取得できます。
"""


def _coverage_md(targets):
    """各国×概念の解決状況をオーバービュー末尾に付す (透明性)。"""
    concepts = [(c, lbl) for c, lbl, _ in registry.CONCEPTS]
    got = {}
    for t in targets:
        got.setdefault(t["country"], set()).add(t["concept"])
    header = "| 国 | " + " | ".join(lbl for _, lbl in concepts) + " |"
    sep = "|" + "|".join(["---"] * (len(concepts) + 1)) + "|"
    lines = ["", "## 解決された主要指標カバレッジ", "",
             f"解決ターゲット総数: **{len(targets)}**（✓=解決, −=該当系列がキャッシュに無い）", "",
             header, sep]
    for country in registry.COUNTRIES:
        g = got.get(country, set())
        if not g:
            continue
        cells = ["✓" if c in g else "−" for c, _ in concepts]
        lines.append(f"| {registry.COUNTRY_LABEL[country]} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("> 「−」は当該国のその指標が file キャッシュに解決できなかったもの"
                 "（例: 米FF金利は明示系列が無く米2年債利回りで代理。加/豪/NZ のコアCPIは独立系列が無い）。")
    return "\n".join(lines)


def _us_matrix_md(eng, cat_idx, us_set):
    keys = [lbl for lbl, _ in us_set]
    ids = {lbl: sid for lbl, sid in us_set}
    freq_of = {lbl: ("Q" if cat_idx.loc[sid, "freq"] in ("quarterly", "annual") else "M")
               for lbl, sid in us_set if sid in cat_idx.index}
    corr = pd.DataFrame(index=keys, columns=keys, dtype=object)
    lag = pd.DataFrame(index=keys, columns=keys, dtype=object)
    for a in keys:
        for b in keys:
            if a == b:
                corr.loc[a, b] = "1.00"; lag.loc[a, b] = 0; continue
            freq = "Q" if "Q" in (freq_of.get(a), freq_of.get(b)) else "M"
            lc = eng.lagcorr(ids[a], ids[b], freq=freq, maxlag=12, minn=16)
            if lc is None:
                corr.loc[a, b] = "."; lag.loc[a, b] = "."
            else:
                corr.loc[a, b] = f"{lc['corr']:+.2f}"; lag.loc[a, b] = lc["lag"]

    def grid_to_html(g, color=False):
        ths = "<th></th>" + "".join(f"<th>{_html.escape(c)}</th>" for c in g.columns)
        rows = []
        for idx, r in g.iterrows():
            tds = [f"<td class='rowhdr'>{_html.escape(str(idx))}</td>"]
            for x in r.values:
                style = ""
                if color:
                    sx = str(x)
                    if sx not in (".", "1.00"):
                        bg = _corr_bg(sx.replace("+", ""))
                        if bg:
                            style = f" style=\"{bg};text-align:center\""
                tds.append(f"<td{style or ' style=\"text-align:center\"'}>{_html.escape(str(x))}</td>")
            rows.append("<tr>" + "".join(tds) + "</tr>")
        return f'<table class="corr-tbl matrix"><thead><tr>{ths}</tr></thead><tbody>{"".join(rows)}</tbody></table>'

    return (corr, lag,
            "# 米国 主要指標クロス相関マトリクス\n\n"
            "行=ターゲット、列=候補。ベストラグでの相関。**正=緑／負(逆相関)=赤**、濃いほど強い。\n\n"
            "## 相関（ベストラグ）\n\n" + grid_to_html(corr, color=True) +
            "\n\n## ベストラグ（期、>0 = 列が行に先行）\n\n" + grid_to_html(lag) +
            "\n\n> 教科書的関係（失業率↔雇用者数の強い逆相関、雇用↔金利の正相関など）が"
            "実データから再現されていれば、エンジンが妥当に動作している証左です。")


def _target_section_md(eng, cat_idx, title, target_id, candidate_ids, freq, full_rows):
    df = rank_target(eng, cat_idx, target_id, candidate_ids, freq=freq)
    if df.empty:
        return f"## {title}\n\n（十分なデータがありません）\n", df
    top = df[df.fdr_sig].head(12)
    robust = df[df.robust_lead].head(15)
    freq_label = "四半期" if freq == "Q" else "月次"
    cols = ["label", "lead_lag", "corr", "corr_lag0", "n", "granger_p"]
    hdr = ["指標", "先行/遅行", "相関", "同時相関", "n", "Granger p"]
    md = [f"## {title}", "", f"系列: `{target_id}` ／ 周期: {freq_label}", ""]
    md.append("### 上位の相関（同時/ベストラグ・FDR有意）")
    md.append(_html_table(top, cols, hdr))
    md.append("")
    md.append("### robust 先行指標（n≥60・|r|≥0.3・Granger p<0.05）")
    if robust.empty:
        md.append("（基準を満たす頑健な先行指標は検出されませんでした）")
    else:
        md.append(_html_table(robust, cols, ["指標", "先行", "相関", "同時相関", "n", "Granger p"]))
    md.append("")
    # 高確度先行 (厳格): 見せかけ(単一レジーム/合わせ込み/長ラグ)を排除した優位性の高い先行のみ
    high = df[df.high_conf].head(15)
    md.append("### 高確度先行指標（厳格: n≥120・|r|≥0.4・先行1-6ヶ月・Granger p<0.01・同時相関と符号整合）")
    if high.empty:
        md.append("（厳格基準を満たす高確度な先行指標はありません）")
    else:
        md.append(_html_table(high, cols, ["指標", "先行", "相関", "同時相関", "n", "Granger p"]))
    md.append("")
    # accumulate full rows for CSV
    d2 = df.copy()
    d2.insert(0, "target", target_id)
    d2.insert(0, "target_title", title)
    full_rows.append(d2)
    return "\n".join(md), df


# ---------------- main build ----------------
def build(as_of: str, scope: str = "full", log=print):
    out = as_of_dir(as_of)
    sections_dir = out / "sections"
    matrices_dir = out / "matrices"
    for d in (sections_dir, matrices_dir):
        d.mkdir(parents=True, exist_ok=True)

    log("[1/5] loading all series ...")
    long_df, cat = loader.build_long_and_catalog()
    cat.to_csv(out / "catalog.csv", index=False, encoding="utf-8-sig")
    eng = Engine(long_df, cat)
    cat_idx = cat.set_index("series_id")
    clean = _clean_ids(cat)
    log(f"      series={len(cat)} clean={len(clean)} obs={len(long_df)}")

    now = pd.Timestamp.now()
    cov_end = min(long_df["date"].max(), now)  # 予測系列の未来日付で範囲が伸びるのを防ぐ
    meta = {
        "as_of": as_of,
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "data_coverage": {"start": str(long_df['date'].min().date()),
                          "end": str(cov_end.date())},
        "n_series": int(cat["series_id"].nunique()),
        "n_clean": len(clean),
    }

    sections = []
    downloads = []
    full_rows = []

    # resolve targets early (overview の coverage 表に使う)
    targets = registry.resolve_targets(cat["series_id"])
    if scope == "quick":
        targets = [t for t in targets if t["country"] == "usa"]
    coverage = _coverage_md(targets)

    # overview
    (sections_dir / "overview.md").write_text(_overview_md(meta) + coverage, encoding="utf-8")
    sections.append({"id": "overview", "title": "概要と読み方", "group": "はじめに"})

    # US matrix
    log("[2/5] US cross-matrix ...")
    us_set = registry.resolve_us_matrix(cat["series_id"])
    corr_g, lag_g, mtx_md = _us_matrix_md(eng, cat_idx, us_set)
    (sections_dir / "us_matrix.md").write_text(mtx_md, encoding="utf-8")
    corr_g.to_csv(matrices_dir / "us_matrix_corr.csv", encoding="utf-8-sig")
    lag_g.to_csv(matrices_dir / "us_matrix_lag.csv", encoding="utf-8-sig")
    sections.append({"id": "us_matrix", "title": "米国 主要指標マトリクス", "group": "クロス分析"})
    downloads += [
        {"name": "us_matrix_corr.csv", "desc": "米主要指標 相関マトリクス"},
        {"name": "us_matrix_lag.csv", "desc": "米主要指標 ベストラグ"},
    ]

    # per-country major indicators
    log("[3/5] per-country major indicators ...")
    by_country = {}
    for t in targets:
        by_country.setdefault(t["country"], []).append(t)
    for country, ts in by_country.items():
        clabel = registry.COUNTRY_LABEL[country]
        parts = [f"# {clabel} 主要指標 — 先行・相関", ""]
        for t in ts:
            freq = "Q" if cat_idx.loc[t["series_id"], "freq"] in ("quarterly", "annual") else "M"
            md, _ = _target_section_md(
                eng, cat_idx, f"{clabel}：{t['concept_label']}",
                t["series_id"], clean, freq, full_rows)
            parts.append(md)
            parts.append("")
        (sections_dir / f"country_{country}.md").write_text("\n".join(parts), encoding="utf-8")
        sections.append({"id": f"country_{country}", "title": f"{clabel} 主要指標", "group": "各国主要指標"})
        log(f"      {country}: {len(ts)} indicators")

    # instruments
    log("[4/5] instruments ...")
    instruments = registry.resolve_instruments(cat["series_id"])
    if scope == "quick":
        instruments = instruments[:4]
    iparts = ["# 主要銘柄 — 先行・相関する経済指標", "",
              "各銘柄の月次リターンに対し、先行/相関する経済指標。", ""]
    for inst in instruments:
        md, _ = _target_section_md(
            eng, cat_idx, f"銘柄：{inst['label']}", inst["series_id"], clean, "M", full_rows)
        iparts.append(md)
        iparts.append("")
    (sections_dir / "instruments.md").write_text("\n".join(iparts), encoding="utf-8")
    sections.append({"id": "instruments", "title": "主要銘柄", "group": "銘柄分析"})

    # combined full CSV
    log("[5/5] writing manifest & downloads ...")
    if full_rows:
        allrows = pd.concat(full_rows, ignore_index=True)
        allrows.to_csv(matrices_dir / "all_rankings.csv", index=False, encoding="utf-8-sig")
        robust_only = allrows[allrows["robust_lead"]]
        robust_only.to_csv(matrices_dir / "robust_leaders.csv", index=False, encoding="utf-8-sig")
        high_only = allrows[allrows["high_conf"]]
        high_only.to_csv(matrices_dir / "high_conf_leaders.csv", index=False, encoding="utf-8-sig")
        downloads += [
            {"name": "all_rankings.csv", "desc": "全ターゲット×全候補 ランキング（フル）"},
            {"name": "robust_leaders.csv", "desc": "robust 先行指標のみ抽出"},
            {"name": "high_conf_leaders.csv", "desc": "高確度先行指標（厳格フィルタ）のみ抽出"},
        ]
    downloads.append({"name": "catalog.csv", "desc": "全系列カタログ", "root": True})

    manifest = {**meta, "sections": sections, "downloads": downloads, "scope": scope}
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # update LATEST pointer
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    latest_pointer().write_text(as_of, encoding="utf-8")
    log(f"done -> {out}")
    return manifest
