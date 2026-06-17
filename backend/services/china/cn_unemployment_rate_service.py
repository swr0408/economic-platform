"""
中国 失業率（Unemployment Rate）サービス

2系列を表示:
- total: 全国城鎮調査失業率 (%)
- youth: 全国城鎮16-24歳労働力失業率 (%)

データソース:
- DB蓄積: nbs_monthly_data テーブル（CSVインポート + プレスリリース蓄積）
  indicator: cn_unemployment_total, cn_unemployment_youth
- 最新値: www.stats.gov.cn/sj/zxfb/ プレスリリース HTML 本文からスクレイピング
  「国民经済」記事に含まれる失業率テキストを正規表現で抽出
- FMP: 次回発表日の取得のみ

CSVは初期インポート済み（csv_import → nbs_monthly_data テーブル）。
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
_FILE_CACHE_DIR = _BASE_DIR / "data" / "cache" / "china" / "employment"
FILE_CACHE_PATH = str(_FILE_CACHE_DIR / "cn_unemployment_rate_cache.json")

REDIS_KEY = "china:cn_unemployment_rate:data"
REDIS_TTL = 86400  # 24h

ECONALPHA_ID = "cn_unemployment_rate"

# DB指標ID
DB_INDICATORS = {
    "total": "cn_unemployment_total",
    "youth": "cn_unemployment_youth",
}

# 手動更新CSV（NBS公式 月次エクスポート、転置ワイド形式）。
# 若年(16-24歳)は NBS が本文/FMP/公開APIから外し data.stats.gov.cn(WAF) のみで
# 配信するため自動取得不可。ここに公式エクスポートを置けば total+youth を取り込む。
# ファイル mtime が更新されると china_employment ローダーが検知して再取得する。
_MANUAL_CSV_PATH = str(
    _BASE_DIR / "data" / "csv_import" / "ChinaUnemployment Rate.csv"
)

# CSV内の系列名（strip後の完全一致）→ DB系列キー
_CSV_SERIES_MAP = {
    "The Urban Surveyed Unemployment Rate (%)": "total",
    "The Urban Surveyed Unemployment Rate of the Population Aged from 16 to 24(%)": "youth",
}

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_month_header(h: str) -> Optional[str]:
    """ヘッダの月表記 "May 2026" → "2026-05-01"。不正は None。"""
    import re
    m = re.match(r"([A-Za-z]+)\.?\s*(\d{4})", h.strip())
    if not m:
        return None
    mon = _MONTH_ABBR.get(m.group(1)[:3].lower())
    if not mon:
        return None
    return f"{int(m.group(2))}-{mon:02d}-01"


def _parse_unemployment_csv() -> Dict[str, Dict[str, float]]:
    """NBS公式 転置ワイドCSV を解析し {"total": {date:val}, "youth": {date:val}} を返す。

    形式（PMI CSVと同形式・ヘッダー無しの転置）:
      行1: Database：Monthly / 行2: Time：... / 行3: Indicators,May 2026,Apr 2026,...
      行4+: 系列名,(各月の値) ...
    値はパーセント数値（空セルはスキップ＝当月未発表）。
    """
    if not os.path.exists(_MANUAL_CSV_PATH):
        return {}
    try:
        with open(_MANUAL_CSV_PATH, encoding="utf-8-sig") as f:
            lines = [ln.rstrip("\n").rstrip("\r") for ln in f]
    except Exception as e:
        logger.warning(f"[Unemployment] Manual CSV read error: {e}")
        return {}

    # ヘッダ行（先頭セルが "Indicators"）を探す
    header_idx = None
    for i, l in enumerate(lines):
        if l.split(",")[0].strip() == "Indicators":
            header_idx = i
            break
    if header_idx is None:
        return {}

    headers = [c.strip() for c in lines[header_idx].split(",")]
    dates = [_parse_month_header(h) for h in headers[1:]]

    out: Dict[str, Dict[str, float]] = {"total": {}, "youth": {}}
    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        key = _CSV_SERIES_MAP.get(parts[0].strip())
        if not key:
            continue
        for i, raw in enumerate(parts[1:]):
            if i >= len(dates) or not dates[i]:
                continue
            v = raw.strip()
            if not v:
                continue
            try:
                out[key][dates[i]] = round(float(v), 1)
            except ValueError:
                continue
    return out


def _import_manual_csv() -> None:
    """手動更新CSVを DB に取り込む（DBと差分のある月のみ・冪等）。

    差分のみ upsert することで、CSV未変更時の無駄なキャッシュ無効化を避ける。
    """
    csv_data = _parse_unemployment_csv()
    if not csv_data:
        return
    from services.china.nbs_db_utils import load_nbs_data, upsert_nbs_data

    for key in ("total", "youth"):
        vals = csv_data.get(key) or {}
        if not vals:
            continue
        existing = load_nbs_data(DB_INDICATORS[key])
        diff = {d: v for d, v in vals.items() if existing.get(d) != v}
        if diff:
            upsert_nbs_data(DB_INDICATORS[key], diff, source="csv")
            logger.info(
                f"[Unemployment] Manual CSV {key}: upserted {len(diff)} changed/new "
                f"({min(diff)}〜{max(diff)})"
            )


def _fetch_and_upsert_from_press_release() -> None:
    """「国民経済」プレスリリースの HTML から失業率をスクレイピングし、DB に UPSERT

    取りこぼし耐性: 直近6件の発表を新→旧順に巡回し、DBに既に当該月の
    失業率が入っていればHTML取得をスキップ。
    """
    from services.china.nbs_press_release_utils import (
        find_recent_releases,
        scrape_unemployment_from_html,
        _data_exists_in_db,
    )
    from services.china.nbs_db_utils import upsert_nbs_data

    releases = find_recent_releases("unemployment", max_pages=2, limit=6)
    if not releases:
        logger.warning("[Unemployment] No press release found")
        return

    for release in releases:
        title = release["title"]
        period = release["period"]

        if not period:
            continue

        year, month = period
        date_str = f"{year}-{month:02d}-01"

        # DB 既存チェック（早期スキップ）
        if _data_exists_in_db(DB_INDICATORS["total"], date_str):
            continue

        logger.info(f"[Unemployment] Fetching: {title} ({date_str})")
        scraped = scrape_unemployment_from_html(release["url"])
        if not scraped:
            logger.warning(f"[Unemployment] No data scraped from {title}")
            continue

        for key in ("total", "youth"):
            val = scraped.get(key)
            if val is not None:
                count = upsert_nbs_data(
                    DB_INDICATORS[key], {date_str: val}, source="api",
                )
                logger.info(f"[Unemployment] {key}={val} for {date_str}, DB upserted {count}")


def _build_data() -> List[Dict[str, Any]]:
    """DBからデータを読み込み + プレスリリース HTML で最新取得→DB蓄積

    手順:
    1. プレスリリース HTML から失業率をスクレイピング → DB UPSERT
    2. DBから全データを読み込み
    3. 日付をキーにマージして時系列構築
    """
    from services.china.nbs_db_utils import load_nbs_multi

    # --- 手動更新CSV(NBS公式エクスポート) → DB蓄積（total + youth、差分のみ）---
    # youth(16-24歳)はこのCSVが唯一の取得源。total も公式値で補強。
    try:
        _import_manual_csv()
    except Exception as e:
        logger.warning(f"[Unemployment] Manual CSV import failed: {e}")

    # --- プレスリリース HTML → DB蓄積 ---
    try:
        _fetch_and_upsert_from_press_release()
    except Exception as e:
        logger.warning(f"[Unemployment] Press release fetch/upsert failed: {e}")

    # --- FMP economic_calendar から total を gap-fill（欠損月のみ・最新フォールバック）---
    # 全国城鎮調査失業率(total)は FMP "Unemployment Rate" に月次実績あり。
    # HTMLスクレイピング失敗時の堅牢なフォールバック＋欠損月の補完。
    # （youth は FMP 非搭載のため別途「分年龄组失业率」リリースから取得）
    try:
        from services.china.nbs_db_utils import backfill_from_fmp_events
        backfill_from_fmp_events(DB_INDICATORS["total"], "Unemployment Rate")
    except Exception as e:
        logger.warning(f"[Unemployment] FMP backfill failed: {e}")

    # --- DBから全データ読み込み ---
    db_data = load_nbs_multi([DB_INDICATORS["total"], DB_INDICATORS["youth"]])
    total_data = db_data.get(DB_INDICATORS["total"], {})
    youth_data = db_data.get(DB_INDICATORS["youth"], {})

    logger.info(f"[Unemployment] DB total: {len(total_data)} records, youth: {len(youth_data)} records")

    # 日付 → {total, youth} のマップを構築
    all_dates = set(total_data.keys()) | set(youth_data.keys())

    # ソートして構築（totalがNoneのレコードは除外）
    result = []
    for date_str in sorted(all_dates):
        total = total_data.get(date_str)
        if total is not None:
            result.append({
                "date": date_str,
                "total": total,
                "youth": youth_data.get(date_str),
            })

    logger.info(f"[Unemployment] Total: {len(result)} records")
    return result


def _get_next_release() -> Optional[Dict[str, Any]]:
    """FMPから次回発表日を取得"""
    try:
        from services.usa.fmp_next_release_utils import get_next_release_from_fmp
        return get_next_release_from_fmp(ECONALPHA_ID, country="CN")
    except Exception as e:
        logger.warning(f"[Unemployment] Failed to get next release: {e}")
        return None


class CnUnemploymentRateService:
    """中国失業率サービス"""

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
            logger.warning(f"[Unemployment] File cache write error: {e}")

    def _build_payload(self) -> Dict[str, Any]:
        data = _build_data()
        latest = data[-1] if data else None
        next_release = _get_next_release()

        return {
            "data": data,
            "latest": latest,
            "metadata": {
                "indicator": "Unemployment Rate",
                "source": "National Bureau of Statistics (NBS)",
                "series": {
                    "total": "全国城鎮調査失業率 (%)",
                    "youth": "16-24歳若年層失業率 (%)",
                },
                "total_records": len(data),
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
        return {"success": True, "message": "Unemployment rate cache invalidated"}

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
cn_unemployment_rate_service = CnUnemploymentRateService()
