"""
RSS 補填スケジューラ + TTL削除ジョブ

FinancialJuice RSS を1時間ごとに取得し、Discord側で取りこぼしたヘッドラインを補填。
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from backend.core.database import get_db_connection
    from backend.services.headlines.headlines_service import ingest_headline, cleanup_expired
    from backend.services.headlines.normalize import normalize_url
except ImportError:
    from core.database import get_db_connection
    from services.headlines.headlines_service import ingest_headline, cleanup_expired
    from services.headlines.normalize import normalize_url

JST = ZoneInfo("Asia/Tokyo")
RSS_URL = "https://www.financialjuice.com/feed.ashx?xy=rss"


class HeadlinesRSSScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._is_running = False
        self._last_etag = None
        self._last_modified = None
        self._last_fetch_at = None
        self._last_items_seen = 0
        self._last_items_inserted = 0

    def _fetch_rss(self) -> dict:
        """RSS取得。ETag/Last-Modified対応。"""
        headers = {"User-Agent": "EconAlpha/1.0"}
        if self._last_etag:
            headers["If-None-Match"] = self._last_etag
        if self._last_modified:
            headers["If-Modified-Since"] = self._last_modified

        resp = httpx.get(RSS_URL, headers=headers, timeout=30, follow_redirects=True)

        result = {
            "status": resp.status_code,
            "etag": resp.headers.get("ETag"),
            "last_modified": resp.headers.get("Last-Modified"),
            "items": [],
        }

        if resp.status_code == 304:
            return result

        if resp.status_code != 200:
            print(f"[RSS] HTTP {resp.status_code}")
            return result

        # ETag/Last-Modified を保存
        if result["etag"]:
            self._last_etag = result["etag"]
        if result["last_modified"]:
            self._last_modified = result["last_modified"]

        # XML パース
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as e:
            print(f"[RSS] Parse error: {e}")
            return result

        channel = root.find("channel")
        if channel is None:
            return result

        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            description = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            pub_date_str = (item.findtext("pubDate") or "").strip()

            # title -> description -> link のフォールバック
            headline_raw = title or description or link
            if not headline_raw:
                continue

            # pubDate パース
            published_at = None
            if pub_date_str:
                try:
                    published_at = parsedate_to_datetime(pub_date_str)
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            result["items"].append({
                "headline_raw": headline_raw,
                "published_at": published_at,
                "external_guid": guid or None,
                "external_link": link or None,
                "embed_title": title if title != headline_raw else None,
                "embed_description": description if description and description != headline_raw else None,
            })

        return result

    def _process_rss(self):
        """RSS取得→DB保存"""
        try:
            result = self._fetch_rss()
            items_seen = len(result["items"])
            items_inserted = 0
            items_deduped = 0

            for item in result["items"]:
                hid = ingest_headline(
                    source_type="rss_backfill",
                    headline_raw=item["headline_raw"],
                    published_at=item["published_at"],
                    external_guid=item["external_guid"],
                    external_link=item["external_link"],
                    embed_title=item.get("embed_title"),
                    embed_description=item.get("embed_description"),
                )
                if hid is not None:
                    items_inserted += 1
                else:
                    items_deduped += 1

            self._last_fetch_at = datetime.now(timezone.utc)
            self._last_items_seen = items_seen
            self._last_items_inserted = items_inserted

            # ログ記録
            self._log_fetch(result["status"], result["etag"], result["last_modified"],
                           items_seen, items_inserted, items_deduped)

            if items_inserted > 0:
                print(f"[RSS] Fetched {items_seen} items, inserted {items_inserted}, deduped {items_deduped}")
            elif result["status"] == 304:
                print("[RSS] Not modified (304)")
            else:
                print(f"[RSS] Fetched {items_seen} items, all deduped")

        except Exception as e:
            print(f"[RSS] Error: {e}")

    def _log_fetch(self, http_status, etag, last_modified, seen, inserted, deduped):
        """rss_fetch_logs に記録"""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO rss_fetch_logs (http_status, etag, last_modified,
                            items_seen, items_inserted, items_deduped)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (http_status, etag, last_modified, seen, inserted, deduped))
                    conn.commit()
        except Exception as e:
            print(f"[RSS] Log error: {e}")

    def _run_cleanup(self):
        """期限切れヘッドライン削除"""
        try:
            count = cleanup_expired()
            if count > 0:
                print(f"[Headlines] Cleaned up {count} expired headlines")
        except Exception as e:
            print(f"[Headlines] Cleanup error: {e}")

    def run_now(self) -> dict:
        """手動実行"""
        self._process_rss()
        return {
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "items_seen": self._last_items_seen,
            "items_inserted": self._last_items_inserted,
        }

    def start(self):
        # 1時間ごとにRSS取得
        self.scheduler.add_job(
            self._process_rss,
            trigger=CronTrigger(minute=0, timezone=JST),
            id="rss_hourly_fetch",
            replace_existing=True,
        )
        # 毎日AM4時に期限切れ削除
        self.scheduler.add_job(
            self._run_cleanup,
            trigger=CronTrigger(hour=4, minute=0, timezone=JST),
            id="headlines_daily_cleanup",
            replace_existing=True,
        )
        self.scheduler.start()
        self._is_running = True

        # 起動時にも1回実行。ただし _process_rss は同期ブロッキング (httpx.get 30s) のため、
        # ここで直接呼ぶと async startup 上でイベントループを止め login 等が応答不能になる。
        # 即時 date ジョブとして登録し、executor のワーカースレッドで実行する。
        self.scheduler.add_job(
            self._process_rss,
            trigger="date",
            run_date=datetime.now(JST) + timedelta(seconds=5),
            id="rss_startup_fetch",
            replace_existing=True,
            misfire_grace_time=600,
        )
        print("[RSS] Headlines RSS Scheduler started (hourly + daily cleanup)")

    def shutdown(self):
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            print("[RSS] Headlines RSS Scheduler stopped")

    def get_status(self) -> dict:
        return {
            "is_running": self._is_running,
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
            "last_items_seen": self._last_items_seen,
            "last_items_inserted": self._last_items_inserted,
        }

    def get_logs(self, limit: int = 20) -> list[dict]:
        """RSS取得ログ"""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM rss_fetch_logs ORDER BY fetched_at DESC LIMIT %s
                    """, (limit,))
                    columns = [desc[0] for desc in cur.description]
                    rows = [dict(zip(columns, r)) for r in cur.fetchall()]
                    for r in rows:
                        if r.get("fetched_at"):
                            r["fetched_at"] = r["fetched_at"].isoformat()
                    return rows
        except Exception:
            return []


headlines_rss_scheduler = HeadlinesRSSScheduler()
