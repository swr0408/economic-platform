"""
韓国半導体輸出 自動更新モジュール

産業通商部 (motir.go.kr, 旧 motie.go.kr) の報道資料ボードから
「정보통신산업(ICT) 수출입 동향」(月次ICTレポート) を取得し、
kr_semiconductor_history.json に新しい月のレコードを追記する。

データソース調査メモ (2026-06-12):
- 記事一覧 (検索付き):
  https://www.motir.go.kr/kor/article/ATCL3f49a5a8c
    ?pageIndex=1&searchCondition=1&searchKeyword=수출입+동향
  → 一覧HTMLに article.view('<id>') 形式でID・タイトル・掲載日が載る
- 記事ページ: https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/<id>/view
- ICTレポート (確報) は本文がHTMLに展開されており、
  「( 반도체 : 319.1 억 달러 , 173.3% ↑ )」(当月ヘッドライン) と
  「반도체 수출 추이 : (’26.1 월 ) 205.5( 102.7 ↑ ) → …」(直近数ヶ月の推移)
  をテキスト抽出できる。値は 억 달러 (= 0.1B USD) → 10で割って USD billion。
  △ または ↓ は前年比マイナス。
- 速報の「수출입 동향」(月初公表) は本文が添付ファイル (HWP/PDF) のみで、
  /attach/down/... は 302 → /error/500 にリダイレクトされDL不可、
  /attach/viewer/... も JPG レンダリングのみのためHTMLからは抽出不可能。
  → 速報はスキップし、ICT確報 (対象月M の翌月中旬公表) のみを取り込む。
- サイトのWAFがTLSハンドシェイク/接続を間欠的にリセットするため、
  urllib3 Retry によるリトライが必須 (体感5割程度の確率でリセットされる)。

発表スケジュール: 対象月Mのレポートは M+1月の中旬 (12〜15日頃) に公表。
"""
import json
import logging
import os
import re
import html as html_mod
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# 履歴JSONファイル (kr_semiconductor_exports_service と共有)
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
HISTORY_FILE = CACHE_DIR / "kr_semiconductor_history.json"

BASE_URL = "https://www.motir.go.kr"
BOARD_PATH = "/kor/article/ATCL3f49a5a8c"  # 報道資料ボード
# 「수출입 동향」(輸出入動向) で検索
SEARCH_QUERY = (
    "?mno=&pageIndex={page}&rowPageC=0&displayAuthor=&searchCategory=0"
    "&schClear=on&startDtD=&endDtD=&searchCondition=1"
    "&searchKeyword=%EC%88%98%EC%B6%9C%EC%9E%85+%EB%8F%99%ED%96%A5"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# 値のサニティ境界 (USD billion / %): パース事故で履歴を壊さないためのガード
VALUE_MIN, VALUE_MAX = 1.0, 150.0
YOY_MIN, YOY_MAX = -90.0, 1000.0
# 既存月の改定は ±15% 以内のみ許容 (誤パースによる上書き防止)
REVISION_MAX_PCT = 15.0


# ============================================================
# HTTP レイヤー
# ============================================================

def _build_session(verify: bool = True) -> requests.Session:
    """WAFの間欠的な接続リセットに耐えるリトライ付きセッションを生成

    TLS検証はデフォルト有効。motir.go.kr の証明書チェーン問題で
    SSLError になった場合のみ、呼び出し側 (_get_session) が
    検証無効のセッションへ一度だけフォールバックする (M-5 対応)。
    """
    session = requests.Session()
    if not verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        session.verify = False
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    })
    retry = Retry(
        total=8,
        connect=8,
        read=8,
        backoff_factor=1.5,
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _get_session() -> requests.Session:
    """TLS検証ありで疎通確認し、証明書チェーン問題のときだけ検証なしへ降格"""
    session = _build_session(verify=True)
    try:
        session.get(BASE_URL, timeout=30)
        return session
    except requests.exceptions.SSLError as e:
        logger.warning(
            f"[KrSemiconductor] TLS verification failed for {BASE_URL} "
            f"({e}); falling back to verify=False (integrity degraded)"
        )
        return _build_session(verify=False)
    except requests.RequestException:
        # SSL以外の失敗 (WAFリセット等) は検証ありのまま返す (リトライは呼び出し側)
        return session


def _html_to_plain(html_text: str) -> str:
    """HTMLをタグ除去・空白正規化したプレーンテキストに変換"""
    plain = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_text, flags=re.S | re.I)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = html_mod.unescape(plain)
    return re.sub(r"\s+", " ", plain)


# ============================================================
# 記事一覧の取得・解析
# ============================================================

# 一覧行: article.view('171830') → タイトル、その後の掲載日 (YYYY-MM-DD)
_LIST_ITEM_RE = re.compile(
    r"article\.view\('(\d+)'\);\"\s*>\s*<i>(.*?)</i>", re.S
)
_LIST_DATE_RE = re.compile(r"<td>\s*(\d{4}-\d{2}-\d{2})\s*</td>")

# タイトル例: 「2026년 4월 정보통신산업(ICT) 수출입 동향」
#            「2025년 연간 및 12월 정보통신산업(ICT) 수출입 동향」
_TITLE_MONTH_RE = re.compile(r"(\d{4})\s*년.*?(\d{1,2})\s*월")


def fetch_article_list(session: requests.Session, page_index: int = 1) -> List[Dict[str, Any]]:
    """検索付き記事一覧ページから ICT 수출입 동향 記事のメタ情報を取得

    Returns: [{"article_id", "title", "ref_month" ("YYYY-MM"), "published_at", "is_ict"}]
    """
    url = BASE_URL + BOARD_PATH + SEARCH_QUERY.format(page=page_index)
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    html_text = resp.text

    items: List[Dict[str, Any]] = []
    matches = list(_LIST_ITEM_RE.finditer(html_text))
    for i, m in enumerate(matches):
        article_id = m.group(1)
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()

        # この記事リンクから次の記事リンクまでの間にある掲載日を拾う
        seg_end = matches[i + 1].start() if i + 1 < len(matches) else len(html_text)
        date_m = _LIST_DATE_RE.search(html_text, m.end(), seg_end)
        published_at = date_m.group(1) if date_m else None

        tm = _TITLE_MONTH_RE.search(title)
        if not tm:
            continue
        year, month = int(tm.group(1)), int(tm.group(2))
        # 「2025년 연간 및 12월 …」のような年間レポートも12月分として扱える
        if not (1 <= month <= 12):
            continue

        items.append({
            "article_id": article_id,
            "title": title,
            "ref_month": f"{year:04d}-{month:02d}",
            "published_at": published_at,
            # ICT確報のみ本文がHTMLで取れる (速報はHWP/PDF添付のみ)
            "is_ict": ("정보통신산업" in title) or ("ICT" in title),
        })
    return items


# ============================================================
# 記事本文から半導体輸出値を抽出
# ============================================================

# 当月ヘッドライン: 「( 반도체 : 319.1 억 달러 , 173.3% ↑ )」
# ※ コロン付きは輸出セクションのヘッドラインのみ (輸入や地域別はコロン無し)
_HEADLINE_RE = re.compile(
    r"반도체\s*[::]\s*([\d,]+(?:\.\d+)?)\s*억\s*(?:달러|불)\s*,\s*"
    r"(△)?\s*([\d,]+(?:\.\d+)?)\s*%?\s*(↑|↓)?"
)

# 추이 (推移) の各要素: 「(’26.1 월 ) 205.5( 102.7 ↑ )」「(2 월 ) 251.5 (160.6 ↑ )」
_TREND_ITEM_RE = re.compile(
    r"\(\s*[\'’‘]?\s*(?:(\d{2})\s*\.)?\s*(\d{1,2})\s*월\s*\)\s*"
    r"([\d,]+(?:\.\d+)?)\s*\(\s*(△)?\s*([\d,]+(?:\.\d+)?)\s*(↑|↓)?\s*\)"
)


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


def _signed_yoy(minus_mark: Optional[str], yoy_str: str, arrow: Optional[str]) -> float:
    """△ または ↓ をマイナス符号として解釈"""
    yoy = _to_float(yoy_str)
    if minus_mark == "△" or arrow == "↓":
        return -yoy
    return yoy


def parse_semiconductor_records(
    plain_text: str, report_year: int, report_month: int
) -> Dict[str, Dict[str, Any]]:
    """ICTレポート本文 (プレーンテキスト) から半導体輸出の月次値を抽出

    Returns: {"YYYY-MM": {"value_usd_billion", "yoy_pct", "raw_text"}}
    値は 억 달러 表記 → /10 で USD billion に変換。
    """
    records: Dict[str, Dict[str, Any]] = {}

    # --- 1) 추이 (直近数ヶ月の推移): 「※ 반도체 수출 추이 ( 억 달러 , %) : …」
    trend_anchor = re.search(r"반도체\s*수출\s*추이", plain_text)
    if trend_anchor:
        # 次のセクション記号 (○/□/•) または600文字までをパース対象にする
        seg_start = trend_anchor.end()
        seg_end_m = re.search(r"[○□•]", plain_text[seg_start:seg_start + 600])
        seg_end = seg_start + (seg_end_m.start() if seg_end_m else 600)
        segment = plain_text[seg_start:seg_end]

        items = _TREND_ITEM_RE.findall(segment)
        if items:
            # 末尾の要素 = レポート対象月として、後ろから年月を割り当てる
            # (途中の要素は「(2 월)」のように年が省略されるため)
            n = len(items)
            year, month = report_year, report_month
            assigned: List[Optional[Tuple[int, int]]] = [None] * n
            ok = True
            for idx in range(n - 1, -1, -1):
                yy_str, mm_str = items[idx][0], items[idx][1]
                mm = int(mm_str)
                if mm != month:
                    # 月の並びがレポート対象月から逆算した連番と一致しない
                    # → パース事故の可能性があるため推移全体を破棄
                    ok = False
                    break
                if yy_str and (2000 + int(yy_str)) != year:
                    ok = False
                    break
                assigned[idx] = (year, month)
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1
            if ok:
                for idx, (yy_mm) in enumerate(assigned):
                    y, m = yy_mm
                    value_eok = _to_float(items[idx][2])
                    yoy = _signed_yoy(items[idx][3], items[idx][4], items[idx][5])
                    ref = f"{y:04d}-{m:02d}"
                    arrow = "↓" if yoy < 0 else "↑"
                    records[ref] = {
                        "value_usd_billion": round(value_eok / 10.0, 2),
                        "yoy_pct": yoy,
                        "raw_text": f"('{y % 100}.{m}월){items[idx][2]}({abs(yoy)}{arrow})",
                    }
            else:
                logger.warning(
                    "[KrSemiUpdater] 추이 month sequence mismatch, trend discarded "
                    f"(report={report_year}-{report_month:02d})"
                )

    # --- 2) 当月ヘッドライン: 「( 반도체 : 319.1 억 달러 , 173.3% ↑ )」
    # 推移よりも信頼度が高いので、対象月はヘッドラインで上書きする
    hm = _HEADLINE_RE.search(plain_text)
    if hm:
        value_eok = _to_float(hm.group(1))
        yoy = _signed_yoy(hm.group(2), hm.group(3), hm.group(4))
        ref = f"{report_year:04d}-{report_month:02d}"
        arrow = "↓" if yoy < 0 else "↑"
        records[ref] = {
            "value_usd_billion": round(value_eok / 10.0, 2),
            "yoy_pct": yoy,
            "raw_text": f"(반도체 : {hm.group(1)}억 달러, {abs(yoy)}%{arrow})",
        }

    return records


def _is_sane(value: Optional[float], yoy: Optional[float]) -> bool:
    """パース事故ガード: 値域チェック"""
    if value is None or yoy is None:
        return False
    return (VALUE_MIN <= value <= VALUE_MAX) and (YOY_MIN <= yoy <= YOY_MAX)


# ============================================================
# 履歴JSONの更新
# ============================================================

def _load_history() -> Dict[str, Any]:
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_history(history: Dict[str, Any]) -> None:
    """tmpファイル経由のアトミック書き込み"""
    tmp_path = str(HISTORY_FILE) + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, str(HISTORY_FILE))


def _expected_latest_month(today: date) -> str:
    """今日時点で公表済みのはずの最新対象月 ("YYYY-MM")

    ICT確報は対象月Mの翌月12〜15日頃に公表されるため、
    12日以降なら前月、それより前なら前々月を期待値とする。
    """
    year, month = today.year, today.month
    # 前月
    month -= 1
    if month == 0:
        year, month = year - 1, 12
    if today.day < 12:
        # まだ前月分は公表前 → 前々月を期待
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"


def update_history(force: bool = False) -> Dict[str, Any]:
    """産業通商部サイトをチェックし、新しい月のレコードを履歴JSONに追記する

    Args:
        force: True なら鮮度ガードをスキップして必ずサイトをチェック

    Returns:
        {"status": "skip"|"no_new"|"updated"|"error", ...}
    """
    try:
        history = _load_history()
    except Exception as e:
        logger.error(f"[KrSemiUpdater] Failed to load history: {e}")
        return {"status": "error", "error": f"history load failed: {e}"}

    existing: Dict[str, Dict[str, Any]] = {
        rec["ref_month"]: rec for rec in history.get("data", []) if rec.get("ref_month")
    }
    last_ref = max(existing.keys()) if existing else ""
    today = datetime.now(JST).date()
    expected = _expected_latest_month(today)

    # 安価なガード: 期待される最新月が既に履歴にあればネットワークアクセス不要
    if not force and last_ref >= expected:
        return {"status": "skip", "last_ref": last_ref, "expected": expected}

    session = _get_session()
    added: List[str] = []
    revised: List[str] = []

    try:
        # 一覧を新しい順に走査 (最大3ページ ≒ 過去半年分の発表をカバー)
        targets: List[Dict[str, Any]] = []
        for page in range(1, 4):
            items = fetch_article_list(session, page_index=page)
            if not items:
                break
            ict_items = [it for it in items if it["is_ict"]]
            targets.extend(it for it in ict_items if it["ref_month"] > last_ref)
            # このページのICT記事が全て既知の月なら、それより古いページは不要
            if ict_items and min(it["ref_month"] for it in ict_items) <= last_ref:
                break

        if not targets:
            return {
                "status": "no_new",
                "last_ref": last_ref,
                "expected": expected,
                "note": "no newer ICT report on site yet",
            }

        # 古い月から順に処理
        targets.sort(key=lambda it: it["ref_month"])
        for it in targets:
            ref_year, ref_month_num = map(int, it["ref_month"].split("-"))
            article_url = f"{BASE_URL}{BOARD_PATH}/{it['article_id']}/view"
            resp = session.get(article_url, timeout=60)
            resp.raise_for_status()
            plain = _html_to_plain(resp.text)

            parsed = parse_semiconductor_records(plain, ref_year, ref_month_num)
            if not parsed:
                logger.warning(
                    f"[KrSemiUpdater] No semiconductor figures parsed from "
                    f"{it['title']} ({article_url})"
                )
                continue

            for ref, rec in sorted(parsed.items()):
                value, yoy = rec["value_usd_billion"], rec["yoy_pct"]
                if not _is_sane(value, yoy):
                    logger.warning(
                        f"[KrSemiUpdater] Insane value skipped {ref}: {value}, {yoy}"
                    )
                    continue

                new_rec = {
                    "ref_month": ref,
                    "value_usd_billion": value,
                    "yoy_pct": yoy,
                    "source_report": "ICT",
                    "published_at": it["published_at"],
                    "source_url": article_url,
                    "raw_text": rec["raw_text"],
                }

                if ref not in existing:
                    # 新しい月 → 追記
                    existing[ref] = new_rec
                    added.append(ref)
                else:
                    # 既存月 → 新しいレポートの改定値のみ反映
                    # (大幅乖離は誤パースとみなして既存値を保持 = 悪化上書き防止)
                    old = existing[ref]
                    old_val = old.get("value_usd_billion")
                    if old_val and value and old_val != value:
                        diff_pct = abs(value - old_val) / old_val * 100
                        if diff_pct <= REVISION_MAX_PCT:
                            existing[ref] = new_rec
                            revised.append(ref)
                        else:
                            logger.warning(
                                f"[KrSemiUpdater] Revision too large for {ref} "
                                f"({old_val} -> {value}, {diff_pct:.1f}%), kept old"
                            )

        if not added and not revised:
            return {
                "status": "no_new",
                "last_ref": last_ref,
                "expected": expected,
                "note": "articles found but no new/revised months",
            }

        # 履歴JSONを再構成して保存
        data = sorted(existing.values(), key=lambda r: r["ref_month"])
        history["data"] = data
        history["total_months"] = len(data)
        history["date_range"] = {
            "start": data[0]["ref_month"],
            "end": data[-1]["ref_month"],
        }
        history["last_auto_update_at"] = datetime.now(JST).isoformat()
        _save_history(history)

        # サービスのRedisキャッシュとダッシュボードキャッシュを無効化
        _invalidate_caches()

        logger.info(
            f"[KrSemiUpdater] History updated: added={added}, revised={revised}"
        )
        return {
            "status": "updated",
            "added": added,
            "revised": revised,
            "last_ref": data[-1]["ref_month"],
        }

    except Exception as e:
        logger.error(f"[KrSemiUpdater] Update failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "added": added}


def _invalidate_caches() -> None:
    """サービスキャッシュ + ダッシュボード集約キャッシュを無効化し再構築"""
    # "global" はPythonの予約語のため通常のimport文が使えない → importlib経由
    import importlib
    mod = importlib.import_module(
        "services.global.kr_semiconductor_exports_service"
    )
    kr_semiconductor_exports_service = mod.kr_semiconductor_exports_service

    try:
        kr_semiconductor_exports_service.invalidate_cache()
        # 履歴JSONから再構築してRedisに載せ直す
        kr_semiconductor_exports_service.get_data(force_refresh=True)
    except Exception as e:
        logger.warning(f"[KrSemiUpdater] Service cache rebuild failed: {e}")

    # ダッシュボード集約ローダーのキャッシュ (main + light/heavy) も削除
    # ※ mainキーを消さないとSWRが古いnull/旧値を返し続ける既知のトラップ
    try:
        from core.redis_client import redis_client
        for key in (
            "global:economy:dashboard:v1",
            "global:economy:dashboard:v1:light",
            "global:economy:dashboard:v1:heavy",
        ):
            redis_client.delete(key)
    except Exception as e:
        logger.warning(f"[KrSemiUpdater] Dashboard cache clear failed: {e}")


if __name__ == "__main__":
    # 手動実行用: backend/ ディレクトリから
    #   python -X utf8 -m services.global.kr_semiconductor_updater [--force]
    import sys
    logging.basicConfig(level=logging.INFO)
    result = update_history(force="--force" in sys.argv)
    print(json.dumps(result, ensure_ascii=False, indent=2))
