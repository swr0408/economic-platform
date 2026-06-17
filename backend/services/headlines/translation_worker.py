"""
翻訳非同期ワーカー - pending のヘッドラインを定期的に翻訳
"""

from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from deep_translator import GoogleTranslator

try:
    from backend.core.database import get_db_connection
except ImportError:
    from core.database import get_db_connection

JST = ZoneInfo("Asia/Tokyo")
BATCH_SIZE = 10


class TranslationWorker:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._is_running = False

    def _translate(self, text: str) -> str:
        """英語→日本語翻訳"""
        if not text or not text.strip():
            return ""
        try:
            if len(text) > 4500:
                text = text[:4500]
            return GoogleTranslator(source='en', target='ja').translate(text)
        except Exception as e:
            print(f"[TranslationWorker] Error: {e}")
            return ""

    def _process_batch(self):
        """pending のヘッドラインを BATCH_SIZE 件翻訳"""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, headline_raw, embed_title, embed_description
                        FROM headlines
                        WHERE translation_status = 'pending'
                        ORDER BY published_at DESC
                        LIMIT %s
                    """, (BATCH_SIZE,))
                    rows = cur.fetchall()

                    if not rows:
                        return

                    for row_id, raw, embed_title, embed_desc in rows:
                        try:
                            ja = self._translate(raw) if raw else ""
                            embed_title_ja = self._translate(embed_title) if embed_title else None
                            embed_desc_ja = self._translate(embed_desc) if embed_desc else None

                            cur.execute("""
                                UPDATE headlines
                                SET headline_ja = %s,
                                    embed_title_ja = %s,
                                    embed_description_ja = %s,
                                    translation_status = 'done'
                                WHERE id = %s
                            """, (ja, embed_title_ja, embed_desc_ja, row_id))
                        except Exception as e:
                            print(f"[TranslationWorker] Failed id={row_id}: {e}")
                            cur.execute("""
                                UPDATE headlines
                                SET translation_status = 'failed'
                                WHERE id = %s
                            """, (row_id,))

                    conn.commit()
                    if rows:
                        print(f"[TranslationWorker] Translated {len(rows)} headlines")

        except Exception as e:
            print(f"[TranslationWorker] Batch error: {e}")

    def retranslate(self, headline_id: int) -> dict:
        """指定ヘッドラインを即時再翻訳する。

        翻訳は外部 API へのブロッキング呼び出しだが、本メソッドは同期エンドポイント
        (FastAPI の ``def`` ハンドラ) からスレッドプール上で呼ばれるため、イベント
        ループを塞がない。翻訳に失敗した場合は ``pending`` に戻し、30 秒間隔の
        バックグラウンドワーカー (``_process_batch``) による再試行に委ねる。

        外部翻訳 API への (秒単位で掛かりうる) ブロッキング呼び出し中は DB 接続を
        保持しない: 読み取り → 翻訳 (接続なし) → 書き込み の 3 段に分け、プール接続を
        外部 I/O の間ずっと占有しないようにしている。
        """
        # 1) 元テキストを短時間の接続で読み取り
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT headline_raw, embed_title, embed_description FROM headlines WHERE id = %s",
                    (headline_id,),
                )
                row = cur.fetchone()
        if not row:
            return {"success": False, "status": "not_found"}
        raw, embed_title, embed_desc = row

        # 2) 翻訳 (DB 接続を保持しない)
        try:
            ja = self._translate(raw) if raw else ""
            embed_title_ja = self._translate(embed_title) if embed_title else None
            embed_desc_ja = self._translate(embed_desc) if embed_desc else None
        except Exception as e:
            print(f"[TranslationWorker] retranslate failed id={headline_id}: {e}")
            ja = ""
            embed_title_ja = embed_desc_ja = None

        # raw があるのに訳が空 = 翻訳 API 失敗。pending に戻しワーカー再試行に委ねる。
        if raw and not ja:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE headlines SET translation_status = 'pending' WHERE id = %s",
                        (headline_id,),
                    )
                    conn.commit()
            return {"success": False, "status": "pending"}

        # 3) 訳を短時間の接続で書き戻し
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE headlines
                    SET headline_ja = %s,
                        embed_title_ja = %s,
                        embed_description_ja = %s,
                        translation_status = 'done'
                    WHERE id = %s
                """, (ja, embed_title_ja, embed_desc_ja, headline_id))
                conn.commit()
        return {"success": True, "status": "done", "headline_ja": ja}

    def start(self):
        self.scheduler.add_job(
            self._process_batch,
            trigger=IntervalTrigger(seconds=30),
            id="translation_batch",
            replace_existing=True,
        )
        self.scheduler.start()
        self._is_running = True
        print("[TranslationWorker] Started (30s interval)")

    def shutdown(self):
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            print("[TranslationWorker] Stopped")

    def get_status(self) -> dict:
        pending = 0
        failed = 0
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT translation_status, COUNT(*) FROM headlines GROUP BY translation_status")
                    for status, count in cur.fetchall():
                        if status == "pending":
                            pending = count
                        elif status == "failed":
                            failed = count
        except Exception:
            pass
        return {"is_running": self._is_running, "pending": pending, "failed": failed}


translation_worker = TranslationWorker()
