"""
ヘッドラインサービス - CRUD + 重複判定
"""

from datetime import datetime, timezone, timedelta

try:
    from backend.core.database import get_db_connection
except ImportError:
    from core.database import get_db_connection

from .normalize import normalize_text, text_hash, generate_dedupe_key
from .classifier import classify, extract_speaker, extract_organization


TTL_DAYS = 3


def ingest_headline(
    source_type: str,
    headline_raw: str,
    published_at: datetime = None,
    source_message_id: int = None,
    source_channel_id: int = None,
    external_guid: str = None,
    external_link: str = None,
    embed_title: str = None,
    embed_description: str = None,
) -> int | None:
    """
    ヘッドラインを取り込む。重複なら None を返す。
    翻訳は行わない（translation_worker に任せる）。
    """
    normalized = normalize_text(headline_raw)
    n_hash = text_hash(normalized)
    dedupe = generate_dedupe_key(
        guid=external_guid,
        link=external_link,
        normalized_text=normalized,
        source_message_id=source_message_id,
        source_type=source_type,
    )

    if not dedupe:
        return None

    # 粗い分類
    full_text = f"{headline_raw} {embed_title or ''} {embed_description or ''}"
    rough_cat = classify(full_text)
    speaker = extract_speaker(full_text)
    org = extract_organization(full_text)

    # expires_at
    pub = published_at or datetime.now(timezone.utc)
    expires = pub + timedelta(days=TTL_DAYS)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO headlines (
                    source_type, source_message_id, source_channel_id,
                    external_guid, external_link,
                    headline_raw, normalized_text, normalized_text_hash,
                    rough_category, speaker_name, organization_name,
                    published_at, translation_status, dedupe_key,
                    canonical_source, expires_at,
                    embed_title, embed_description
                ) VALUES (
                    %(source_type)s, %(source_message_id)s, %(source_channel_id)s,
                    %(external_guid)s, %(external_link)s,
                    %(headline_raw)s, %(normalized)s, %(n_hash)s,
                    %(rough_cat)s, %(speaker)s, %(org)s,
                    %(published_at)s, 'pending', %(dedupe)s,
                    %(source_type)s, %(expires)s,
                    %(embed_title)s, %(embed_description)s
                )
                ON CONFLICT (dedupe_key) DO UPDATE SET
                    canonical_source = CASE
                        WHEN headlines.source_type = 'rss_backfill' AND %(source_type)s = 'discord'
                        THEN 'discord'
                        ELSE headlines.canonical_source
                    END
                RETURNING id
            """, {
                "source_type": source_type,
                "source_message_id": source_message_id,
                "source_channel_id": source_channel_id,
                "external_guid": external_guid,
                "external_link": external_link,
                "headline_raw": headline_raw,
                "normalized": normalized,
                "n_hash": n_hash,
                "rough_cat": rough_cat,
                "speaker": speaker,
                "org": org,
                "published_at": pub,
                "dedupe": dedupe,
                "expires": expires,
                "embed_title": embed_title,
                "embed_description": embed_description,
            })
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None


def get_headlines(
    limit: int = 20,
    offset: int = 0,
    source: str = None,
    rough_category: str = None,
    speaker: str = None,
    saved_only: bool = False,
    date_from: str = None,
    date_to: str = None,
    q: str = None,
) -> dict:
    """ヘッドライン一覧を取得"""
    conditions = []
    params = {}

    if source:
        conditions.append("h.source_type = %(source)s")
        params["source"] = source
    if rough_category:
        conditions.append("h.rough_category = %(rough_category)s")
        params["rough_category"] = rough_category
    if speaker:
        conditions.append("h.speaker_name ILIKE %(speaker)s")
        params["speaker"] = f"%{speaker}%"
    if saved_only:
        conditions.append("EXISTS (SELECT 1 FROM saved_headlines sh WHERE sh.headline_id = h.id)")
    if date_from:
        conditions.append("h.published_at >= %(date_from)s")
        params["date_from"] = date_from
    if date_to:
        conditions.append("h.published_at <= %(date_to)s")
        params["date_to"] = date_to
    if q:
        conditions.append("(h.headline_raw ILIKE %(q)s OR h.headline_ja ILIKE %(q)s)")
        params["q"] = f"%{q}%"

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT h.*,
                    EXISTS (SELECT 1 FROM saved_headlines sh WHERE sh.headline_id = h.id) AS is_saved
                FROM headlines h
                {where}
                ORDER BY h.published_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, {**params, "limit": limit, "offset": offset})
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

            cur.execute(f"SELECT COUNT(*) FROM headlines h {where}", params)
            total = cur.fetchone()[0]

    for row in rows:
        for key in ("published_at", "ingested_at", "expires_at"):
            if row.get(key):
                row[key] = row[key].isoformat()

    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def get_headline_by_id(headline_id: int) -> dict | None:
    """ヘッドライン詳細を取得"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT h.*,
                    EXISTS (SELECT 1 FROM saved_headlines sh WHERE sh.headline_id = h.id) AS is_saved
                FROM headlines h WHERE h.id = %s
            """, (headline_id,))
            if cur.rowcount == 0:
                return None
            columns = [desc[0] for desc in cur.description]
            row = dict(zip(columns, cur.fetchone()))

            # 保存カテゴリも取得
            cur.execute("""
                SELECT sh.id as saved_id, sh.category_id, c.name as category_name,
                       c.color, sh.saved_note, sh.saved_at
                FROM saved_headlines sh
                JOIN categories c ON c.id = sh.category_id
                WHERE sh.headline_id = %s
            """, (headline_id,))
            cols2 = [desc[0] for desc in cur.description]
            row["saved_categories"] = [dict(zip(cols2, r)) for r in cur.fetchall()]

    for key in ("published_at", "ingested_at", "expires_at"):
        if row.get(key):
            row[key] = row[key].isoformat()
    for sc in row.get("saved_categories", []):
        if sc.get("saved_at"):
            sc["saved_at"] = sc["saved_at"].isoformat()

    return row


def save_headline(headline_id: int, category_ids: list[int] = None, new_category_name: str = None, note: str = None) -> dict:
    """ヘッドラインをカテゴリに保存（snapshot付き）"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 元ヘッドラインを取得
            cur.execute("SELECT headline_raw, headline_ja, source_type, published_at FROM headlines WHERE id = %s", (headline_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "Headline not found"}
            raw, ja, src, pub = row

            ids = list(category_ids or [])

            # 新規カテゴリ作成
            if new_category_name and new_category_name.strip():
                cur.execute("""
                    INSERT INTO categories (name) VALUES (%s)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                """, (new_category_name.strip(),))
                ids.append(cur.fetchone()[0])

            if not ids:
                return {"error": "No categories specified"}

            saved = []
            for cid in ids:
                cur.execute("""
                    INSERT INTO saved_headlines (headline_id, category_id, saved_note,
                        snapshot_raw, snapshot_ja, snapshot_source_type, snapshot_published_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (headline_id, category_id) DO UPDATE SET saved_note = EXCLUDED.saved_note
                    RETURNING id
                """, (headline_id, cid, note, raw, ja, src, pub))
                saved.append(cur.fetchone()[0])

            conn.commit()
            return {"saved_ids": saved}


def unsave_headline(saved_id: int) -> bool:
    """保存を解除"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM saved_headlines WHERE id = %s", (saved_id,))
            conn.commit()
            return cur.rowcount > 0


def get_categories() -> list[dict]:
    """カテゴリ一覧"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.*, COUNT(sh.id) as headline_count
                FROM categories c
                LEFT JOIN saved_headlines sh ON sh.category_id = c.id
                GROUP BY c.id
                ORDER BY c.sort_order, c.name
            """)
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, r)) for r in cur.fetchall()]
            for r in rows:
                if r.get("created_at"):
                    r["created_at"] = r["created_at"].isoformat()
            return rows


def create_category(name: str, color: str = "#3b82f6") -> dict:
    """カテゴリ作成"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO categories (name, color) VALUES (%s, %s)
                RETURNING id, name, color, sort_order
            """, (name, color))
            row = cur.fetchone()
            conn.commit()
            return {"id": row[0], "name": row[1], "color": row[2], "sort_order": row[3]}


def update_category(category_id: int, name: str = None, color: str = None, sort_order: int = None) -> bool:
    """カテゴリ更新"""
    updates = []
    params = {"id": category_id}
    if name is not None:
        updates.append("name = %(name)s")
        params["name"] = name
    if color is not None:
        updates.append("color = %(color)s")
        params["color"] = color
    if sort_order is not None:
        updates.append("sort_order = %(sort_order)s")
        params["sort_order"] = sort_order
    if not updates:
        return False
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = %(id)s", params)
            conn.commit()
            return cur.rowcount > 0


def delete_category(category_id: int) -> bool:
    """カテゴリ削除"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
            conn.commit()
            return cur.rowcount > 0


def cleanup_expired() -> int:
    """期限切れヘッドラインを削除（保存済みは除く）"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM headlines
                WHERE expires_at < NOW()
                AND NOT EXISTS (SELECT 1 FROM saved_headlines sh WHERE sh.headline_id = headlines.id)
            """)
            count = cur.rowcount
            conn.commit()
            return count
