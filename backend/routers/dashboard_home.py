"""
ホームダッシュボード用 API

- GET /api/dashboard/recent-updates
  backend/data/cache/{country}/{category}/*.json を走査し、
  各キャッシュの last_updated を集計して最近更新された指標を返す。

  Phase 1 (このファイル):
    - 最終更新時刻、国、カテゴリ、指標ID、スラッグ、ラベルのみを返す
    - 値・前回値・差分はキャッシュスキーマが指標ごとに異なるため、
      個別パーサーを指標ごとに順次追加する方針 (Phase 2+)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

try:
    from backend.config import CACHE_DIR  # type: ignore[attr-defined]
except Exception:
    # フォールバック: config に CACHE_DIR が無い場合は相対解決
    CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

try:
    from backend.services.dashboard.indicator_labels import get_indicator_label
except ImportError:
    from services.dashboard.indicator_labels import get_indicator_label  # type: ignore


router = APIRouter(prefix="/api/dashboard", tags=["DashboardHome"])


# ---------------------------------------------------------------------------
# 国コード → 表示名
# ---------------------------------------------------------------------------

COUNTRY_LABELS: Dict[str, Dict[str, str]] = {
    "usa": {"label": "アメリカ", "iso": "us"},
    "japan": {"label": "日本", "iso": "jp"},
    "eurozone": {"label": "ユーロ圏", "iso": "eu"},
    "uk": {"label": "イギリス", "iso": "gb"},
    "china": {"label": "中国", "iso": "cn"},
    "canada": {"label": "カナダ", "iso": "ca"},
    "australia": {"label": "オーストラリア", "iso": "au"},
    "newzealand": {"label": "ニュージーランド", "iso": "nz"},
    "switzerland": {"label": "スイス", "iso": "ch"},
    "global": {"label": "グローバル", "iso": "un"},
    "market": {"label": "マーケット", "iso": ""},
}

# 対応対象 (マクロ指標のみ)。market は Ticker Tape で代替するので除外。
TARGET_COUNTRIES = [
    "usa",
    "japan",
    "eurozone",
    "uk",
    "china",
    "canada",
    "australia",
    "newzealand",
    "switzerland",
]


CATEGORY_LABELS: Dict[str, str] = {
    "policy": "金融政策",
    "monetary_policy": "金融政策",
    "economy": "景気",
    "inflation": "物価",
    "price": "物価",
    "employment": "雇用",
    "consumer": "消費",
    "consumer_sentiment": "消費者心理",
    "consumption": "消費",
    "housing": "住宅",
    "fiscal": "財政",
    "trade": "貿易",
    "derivatives": "デリバティブ",
    "economy_watcher": "景気ウォッチャー",
    "calendar": "カレンダー",
}


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------


def _slug_to_label(slug: str) -> str:
    """ファイル名スラッグから簡易な人間可読ラベルを生成する。
    例: "ism_manufacturing" -> "Ism Manufacturing"
        "cpi" -> "Cpi"
    日本語マッピングは後続で indicator_registry として段階的に追加する。
    """
    name = slug.replace("_cache", "")
    name = name.replace("_", " ").strip()
    return " ".join(w.capitalize() for w in name.split())


def _parse_iso_datetime(raw: Any) -> Optional[datetime]:
    """ISO 8601 文字列を tz-aware datetime に変換する。失敗時は None。"""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        # Python は "Z" をそのまま解析できないので置換
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _extract_last_updated(payload: Dict[str, Any]) -> Optional[datetime]:
    """キャッシュ dict から最終更新時刻を抽出する (複数キーを試す)。"""
    for key in ("last_updated", "updated_at", "fetched_at", "generated_at"):
        if key in payload:
            dt = _parse_iso_datetime(payload[key])
            if dt is not None:
                return dt
    return None


def _to_float(val: Any) -> Optional[float]:
    """任意の値を float に変換。失敗時は None。"""
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val) if not (isinstance(val, float) and (val != val)) else None
    if isinstance(val, str):
        s = val.strip().replace(",", "")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _extract_latest_value(payload: Dict[str, Any]) -> Dict[str, Any]:
    """キャッシュ dict から最新値と前回値を抽出する。

    対応スキーマ (優先度順):
      1. payload['latest'] = {'value': X, 'previous': Y, ...}
         → value=X, previous=Y, change=X-Y
      2. payload['latest'] = {'value': X, 'yoy': Y}
         → value=X, yoy=Y (前回比は未取得)
      3. payload['latest'] = {'value': X}
         → value=X のみ
      4. payload['data'] = [{'value': ...}, ...] で末尾2要素を使う
         → value=arr[-1].value, previous=arr[-2].value

    返却:
      {
        'value': float | None,
        'previous': float | None,
        'change': float | None,
        'change_pct': float | None,
        'yoy': float | None,
        'mom': float | None,
        'unit': str | None (将来拡張用),
      }
    """
    result: Dict[str, Any] = {
        "value": None,
        "previous": None,
        "change": None,
        "change_pct": None,
        "yoy": None,
        "mom": None,
        "unit": None,
    }

    latest = payload.get("latest")
    if isinstance(latest, dict):
        result["value"] = _to_float(latest.get("value"))
        result["previous"] = _to_float(latest.get("previous"))
        result["yoy"] = _to_float(latest.get("yoy"))
        result["mom"] = _to_float(latest.get("mom"))

    # previous が取得できなかった場合、data 配列末尾から推定
    if result["previous"] is None and result["value"] is not None:
        data = payload.get("data")
        if isinstance(data, list) and len(data) >= 2:
            prev_item = data[-2]
            if isinstance(prev_item, dict):
                result["previous"] = _to_float(prev_item.get("value"))

    # value が latest に無かった場合、data 配列末尾から推定
    if result["value"] is None:
        data = payload.get("data")
        if isinstance(data, list) and len(data) >= 1:
            last_item = data[-1]
            if isinstance(last_item, dict):
                result["value"] = _to_float(last_item.get("value"))
                if result["previous"] is None and len(data) >= 2:
                    prev_item = data[-2]
                    if isinstance(prev_item, dict):
                        result["previous"] = _to_float(prev_item.get("value"))

    # 差分を計算
    if result["value"] is not None and result["previous"] is not None:
        result["change"] = round(result["value"] - result["previous"], 4)
        if result["previous"] != 0:
            result["change_pct"] = round(
                (result["value"] - result["previous"]) / abs(result["previous"]) * 100,
                2,
            )

    return result


# ---------------------------------------------------------------------------
# 走査ロジック
# ---------------------------------------------------------------------------


def _iter_cache_entries(countries: List[str]) -> List[Dict[str, Any]]:
    """指定国のキャッシュファイルを走査してエントリのリストを返す。"""
    entries: List[Dict[str, Any]] = []
    root = Path(CACHE_DIR)
    if not root.exists():
        return entries

    for country in countries:
        country_dir = root / country
        if not country_dir.is_dir():
            continue
        # category ディレクトリを走査 (policy / economy / inflation ...)
        for category_dir in country_dir.iterdir():
            if not category_dir.is_dir():
                continue
            category = category_dir.name
            for json_path in category_dir.glob("*.json"):
                if not json_path.name.endswith("_cache.json") and not json_path.name.endswith(".json"):
                    continue
                # ファイル名ベースの指標ID
                stem = json_path.stem
                indicator_id = re.sub(r"_cache$", "", stem)

                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue

                last_updated = _extract_last_updated(payload)
                if last_updated is None:
                    continue

                # 日本語ラベルを辞書から解決、なければスラッグを整形
                jp_label = get_indicator_label(indicator_id)
                # 遷移ルート: /country/{country}/{category}#{anchor}
                # anchor はスネークケース → ケバブケース (countryData.tsx の code 形式)
                anchor = indicator_id.replace("_", "-")
                route = f"/country/{country}/{category}"
                # 値・前回比の抽出 (取れなかった項目は None)
                values = _extract_latest_value(payload)
                entry = {
                    "country": country,
                    "country_label": COUNTRY_LABELS.get(country, {}).get("label", country),
                    "country_iso": COUNTRY_LABELS.get(country, {}).get("iso", ""),
                    "category": category,
                    "category_label": CATEGORY_LABELS.get(category, category),
                    "indicator_id": indicator_id,
                    "indicator_label": jp_label or _slug_to_label(indicator_id),
                    "last_updated": last_updated.astimezone(timezone.utc).isoformat(),
                    "route": route,
                    "anchor": anchor,
                    "value": values["value"],
                    "previous": values["previous"],
                    "change": values["change"],
                    "change_pct": values["change_pct"],
                    "yoy": values["yoy"],
                    "mom": values["mom"],
                }
                entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.get("/recent-updates")
def api_recent_updates(
    country: str = Query("all", description="フィルタする国コード、all で全件"),
    since_hours: int = Query(0, ge=0, le=24 * 30, description="直近 N 時間に絞る (0 = フィルタなし)"),
    limit: int = Query(50, ge=1, le=500, description="最大件数"),
) -> Dict[str, Any]:
    """直近更新された経済指標リストを返す。

    レスポンス:
        {
          "updates": [...],
          "counts_by_country": {usa: 5, japan: 3, ...},
          "generated_at": "2026-04-09T10:00:00+00:00"
        }
    """
    if country == "all":
        target_countries = TARGET_COUNTRIES
    elif country in TARGET_COUNTRIES:
        target_countries = [country]
    else:
        return {
            "updates": [],
            "counts_by_country": {},
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    entries = _iter_cache_entries(target_countries)

    # since_hours フィルタ
    if since_hours > 0:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=since_hours)
        entries = [
            e for e in entries
            if _parse_iso_datetime(e["last_updated"]) is not None
            and _parse_iso_datetime(e["last_updated"]) >= cutoff  # type: ignore[operator]
        ]

    # 新しい順にソート
    entries.sort(
        key=lambda e: _parse_iso_datetime(e["last_updated"]) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    # 件数カウント (フィルタ前・国別)
    counts_by_country: Dict[str, int] = {}
    for e in entries:
        counts_by_country[e["country"]] = counts_by_country.get(e["country"], 0) + 1

    trimmed = entries[:limit]

    return {
        "updates": trimmed,
        "counts_by_country": counts_by_country,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
