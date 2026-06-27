"""
ヘッドラインサービス - CRUD + 重複判定
"""

import uuid
from datetime import datetime, timezone, timedelta

import psycopg2

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
            # クロスソース重複排除（Discord/RSS 間）
            if normalized and source_type == "rss_backfill":
                # RSS取り込み時: 正規化テキストがDiscord側レコードに含まれるかチェック
                # （Discordは複数ヘッドラインを1メッセージに連結するため、ハッシュ一致ではなく含有チェック）
                cur.execute("""
                    SELECT id FROM headlines
                    WHERE source_type = 'discord'
                    AND (normalized_text_hash = %s
                         OR normalized_text ILIKE '%%' || %s || '%%')
                    LIMIT 1
                """, (n_hash, normalized[:100]))
                if cur.fetchone():
                    return None
            elif normalized and source_type == "discord":
                # Discord取り込み時: 同内容のRSSレコードがあればcanonical_sourceを更新して削除
                cur.execute("""
                    SELECT id FROM headlines
                    WHERE source_type = 'rss_backfill'
                    AND normalized_text_hash = %s
                    LIMIT 1
                """, (n_hash,))
                rss_row = cur.fetchone()
                if rss_row:
                    cur.execute("DELETE FROM headlines WHERE id = %s AND NOT EXISTS (SELECT 1 FROM saved_headlines WHERE headline_id = %s)", (rss_row[0], rss_row[0]))
                    conn.commit()

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
    saved_category_name: str = None,
    saved_category_id: int = None,
    saved_category_prefix: str = None,
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
    if saved_category_name:
        conditions.append("""EXISTS (
            SELECT 1 FROM saved_headlines sh
            JOIN categories c ON c.id = sh.category_id
            WHERE sh.headline_id = h.id AND c.name = %(saved_category_name)s
        )""")
        params["saved_category_name"] = saved_category_name
    if saved_category_id:
        # 指定カテゴリ自身 + その子カテゴリに保存されたヘッドラインを含む
        conditions.append("""EXISTS (
            SELECT 1 FROM saved_headlines sh
            WHERE sh.headline_id = h.id
            AND sh.category_id IN (
                SELECT id FROM categories WHERE id = %(saved_category_id)s OR parent_id = %(saved_category_id)s
            )
        )""")
        params["saved_category_id"] = saved_category_id
    if saved_category_prefix:
        # カテゴリ名が指定プレフィックスで始まるもの、またはその子カテゴリに保存されたヘッドライン
        conditions.append("""EXISTS (
            SELECT 1 FROM saved_headlines sh
            JOIN categories c ON c.id = sh.category_id
            WHERE sh.headline_id = h.id
            AND (c.name LIKE %(saved_category_prefix)s
                 OR c.parent_id IN (SELECT id FROM categories WHERE name LIKE %(saved_category_prefix)s))
        )""")
        params["saved_category_prefix"] = f"{saved_category_prefix}%"
    if date_from:
        conditions.append("h.published_at >= %(date_from)s")
        params["date_from"] = date_from
    if date_to:
        conditions.append("h.published_at <= %(date_to)s")
        params["date_to"] = date_to
    if q:
        # 「文言が一致していればいい」: 表示している全テキスト列を横断して部分一致検索する。
        # ILIKE は大文字小文字を区別しない (英語の大小文字差は無視)。NULL 列は OR 内で
        # 自然に不一致扱いになる。speaker_name / organization_name / embed 各列も対象に含め、
        # 画面に見える文言ならどれでもヒットするようにする。
        conditions.append(
            "("
            "h.headline_raw ILIKE %(q)s OR h.headline_ja ILIKE %(q)s "
            "OR h.speaker_name ILIKE %(q)s OR h.organization_name ILIKE %(q)s "
            "OR h.embed_title ILIKE %(q)s OR h.embed_title_ja ILIKE %(q)s "
            "OR h.embed_description ILIKE %(q)s OR h.embed_description_ja ILIKE %(q)s"
            ")"
        )
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

            # 保存カテゴリ情報を一括取得
            if rows:
                headline_ids = [r["id"] for r in rows]
                cur.execute("""
                    SELECT sh.headline_id, sh.id as saved_id, sh.category_id,
                           c.name as category_name, c.color as category_color,
                           c.parent_id as category_parent_id,
                           sh.saved_note as note, sh.saved_at, sh.sort_order
                    FROM saved_headlines sh
                    JOIN categories c ON c.id = sh.category_id
                    WHERE sh.headline_id = ANY(%s)
                """, (headline_ids,))
                sc_cols = [desc[0] for desc in cur.description]
                sc_rows = [dict(zip(sc_cols, r)) for r in cur.fetchall()]

                sc_map: dict[int, list] = {}
                for sc in sc_rows:
                    hid = sc.pop("headline_id")
                    if sc.get("saved_at"):
                        sc["saved_at"] = sc["saved_at"].isoformat()
                    sc_map.setdefault(hid, []).append(sc)

                for row in rows:
                    row["saved_categories"] = sc_map.get(row["id"], [])

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
                       c.color as category_color, c.parent_id as category_parent_id,
                       sh.saved_note as note, sh.saved_at, sh.sort_order
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


def save_headline(
    headline_id: int,
    category_ids: list[int] = None,
    new_category_name: str = None,
    note: str = None,
    is_public_visible: bool = False,
) -> dict:
    """ヘッドラインをカテゴリに保存（snapshot付き）

    Args:
        is_public_visible: True の場合、/api/headlines/public で全ロール (general 含む)
            に公開される。master のみが指定可能 (router 側で保証)。
    """
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
                        snapshot_raw, snapshot_ja, snapshot_source_type, snapshot_published_at,
                        is_public_visible)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (headline_id, category_id) DO UPDATE SET
                        saved_note = EXCLUDED.saved_note,
                        is_public_visible = EXCLUDED.is_public_visible
                    RETURNING id
                """, (headline_id, cid, note, raw, ja, src, pub, is_public_visible))
                saved.append(cur.fetchone()[0])

            conn.commit()
            return {"saved_ids": saved}


def create_manual_headline(
    content: str,
    rough_category: str = None,
    category_ids: list[int] = None,
    new_category_name: str = None,
    note: str = None,
    is_public_visible: bool = False,
    speaker_name: str = None,
    organization: str = None,
    external_link: str = None,
) -> dict:
    """手動でヘッドラインを作成し、指定カテゴリに保存する (master 限定)

    RSS/Discord 由来ではなく master が手入力したヘッドライン。
    source_type='manual'、翻訳済み (translation_status='done') として登録し、
    そのまま save_headline と同じ形でカテゴリへ保存する。
    各国ページのサイドバー (savedOnly + prefix) に表示させるには
    カテゴリ指定 (category_ids または new_category_name) が必須。
    """
    content = (content or "").strip()
    if not content:
        return {"error": "Content is required"}

    ids = list(category_ids or [])
    has_new = bool(new_category_name and new_category_name.strip())
    if not ids and not has_new:
        return {"error": "No categories specified"}

    normalized = normalize_text(content)
    n_hash = text_hash(normalized)
    now = datetime.now(timezone.utc)
    # 手入力は重複排除しない。一意な dedupe_key を割り当てる。
    dedupe = f"manual:{uuid.uuid4().hex}"
    # 手動ヘッドラインは保存前提なので実質期限切れしないが、念のため長期に設定
    expires = now + timedelta(days=3650)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO headlines (
                    source_type, headline_raw, headline_ja,
                    normalized_text, normalized_text_hash,
                    rough_category, speaker_name, organization_name,
                    external_link, published_at, translation_status,
                    dedupe_key, canonical_source, expires_at
                ) VALUES (
                    'manual', %(content)s, %(content)s,
                    %(normalized)s, %(n_hash)s,
                    %(rough)s, %(speaker)s, %(org)s,
                    %(link)s, %(now)s, 'done',
                    %(dedupe)s, 'manual', %(expires)s
                )
                RETURNING id
            """, {
                "content": content,
                "normalized": normalized,
                "n_hash": n_hash,
                "rough": rough_category,
                "speaker": (speaker_name or None),
                "org": (organization or None),
                "link": (external_link or None),
                "now": now,
                "dedupe": dedupe,
                "expires": expires,
            })
            headline_id = cur.fetchone()[0]

            # 新規トップレベルカテゴリ
            if has_new:
                cur.execute("""
                    INSERT INTO categories (name) VALUES (%s)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                """, (new_category_name.strip(),))
                ids.append(cur.fetchone()[0])

            saved = []
            for cid in ids:
                cur.execute("""
                    INSERT INTO saved_headlines (headline_id, category_id, saved_note,
                        snapshot_raw, snapshot_ja, snapshot_source_type, snapshot_published_at,
                        is_public_visible)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (headline_id, category_id) DO UPDATE SET
                        saved_note = EXCLUDED.saved_note,
                        is_public_visible = EXCLUDED.is_public_visible
                    RETURNING id
                """, (headline_id, cid, note, content, content, 'manual', now, is_public_visible))
                saved.append(cur.fetchone()[0])

            conn.commit()
            return {"headline_id": headline_id, "saved_ids": saved}


def reorder_saved_headlines(category_id: int, saved_ids: list[int]) -> dict:
    """カテゴリ内の保存ヘッドラインの並び順を保存 (配列の添字 = sort_order)"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for idx, sid in enumerate(saved_ids):
                cur.execute("""
                    UPDATE saved_headlines SET sort_order = %s
                    WHERE id = %s AND category_id = %s
                """, (idx, sid, category_id))
            conn.commit()
    return {"success": True, "count": len(saved_ids)}


def reorder_sidebar_entries(entries: list[dict]) -> dict:
    """サイドバーセクション内の表示順を一括保存。
    直下ヘッドライン (saved_headlines) と子カテゴリブロック (categories) が
    混在するため、同一の連番 sortOrder を両テーブルに振り分けて保存する。

    entries: [{"type": "saved"|"category", "id": int, "sortOrder": int}, ...]
    """
    saved_count = 0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for e in entries:
                etype = e.get("type")
                if etype == "saved":
                    cur.execute(
                        "UPDATE saved_headlines SET sort_order = %s WHERE id = %s",
                        (e["sortOrder"], e["id"]),
                    )
                    saved_count += cur.rowcount
                elif etype == "category":
                    cur.execute(
                        "UPDATE categories SET sort_order = %s WHERE id = %s",
                        (e["sortOrder"], e["id"]),
                    )
                    saved_count += cur.rowcount
            conn.commit()
    return {"success": True, "count": saved_count}


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


def _ensure_category_constraints(cur) -> None:
    """カテゴリ名の一意制約を「親ごとの一意」に移行する（冪等）。

    旧: name 単体のグローバル UNIQUE (categories_name_key)
        → 同名カテゴリを別の親の下に作れず、UI からの子カテゴリ作成が
          UNIQUE 違反 → 500 になっていた。
    新: 子カテゴリは (parent_id, name) で一意 / 最上位 (parent_id IS NULL) は name で一意。
        → 例えば「経済」配下と「雇用」配下の両方に「ベージュブック」を作成できる。
          シードの最上位カテゴリ（"USA: 金融政策" 等のプレフィックス命名）の一意性は維持。
    """
    cur.execute("ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key")
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS categories_toplevel_name_uniq "
        "ON categories (name) WHERE parent_id IS NULL"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS categories_child_parent_name_uniq "
        "ON categories (parent_id, name) WHERE parent_id IS NOT NULL"
    )


def create_category(name: str, color: str = "#3b82f6", parent_id: int = None) -> dict:
    """カテゴリ作成。

    同じ親の下に同名が既にある場合は UNIQUE 違反を捕捉し、500 ではなく
    {"error": ...} を返す（ルート側で 409 に変換）。別の親の下なら作成できる。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            _ensure_category_constraints(cur)
            try:
                cur.execute("""
                    INSERT INTO categories (name, color, parent_id) VALUES (%s, %s, %s)
                    RETURNING id, name, color, sort_order, parent_id
                """, (name, color, parent_id))
                row = cur.fetchone()
                conn.commit()
                return {"id": row[0], "name": row[1], "color": row[2], "sort_order": row[3], "parent_id": row[4]}
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                return {"error": "同じ階層に同名のカテゴリが既に存在します"}


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
            try:
                cur.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = %(id)s", params)
                conn.commit()
            except psycopg2.errors.UniqueViolation:
                # 同じ親の下に同名へ改名 → UNIQUE(parent_id, name) 違反。
                # create_category と同様に 500 ではなく 409 へ変換できるよう ValueError を送出。
                conn.rollback()
                raise ValueError("同じ階層に同名のカテゴリが既に存在します")
            return cur.rowcount > 0


def delete_category(category_id: int) -> bool:
    """カテゴリ削除 (子カテゴリと保存レコードも明示的に削除し、FK制約エラーを防ぐ)"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM categories WHERE id = %s OR parent_id = %s",
                (category_id, category_id),
            )
            ids = [r[0] for r in cur.fetchall()]
            if not ids:
                return False
            cur.execute("DELETE FROM saved_headlines WHERE category_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM categories WHERE id = ANY(%s)", (ids,))
            deleted = cur.rowcount
            conn.commit()
            return deleted > 0


def _upsert_category(cur, name: str, color: str, sort_order: int, parent_id: int = None) -> int:
    """カテゴリをUPSERT（既存ならIDを返す、なければ作成）。

    一意制約が「親ごと」に変わったため、ON CONFLICT の対象を parent_id の有無で切り替える。
    """
    if parent_id is None:
        cur.execute("""
            INSERT INTO categories (name, color, sort_order, parent_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) WHERE parent_id IS NULL
            DO UPDATE SET parent_id = COALESCE(categories.parent_id, EXCLUDED.parent_id)
            RETURNING id
        """, (name, color, sort_order, parent_id))
    else:
        cur.execute("""
            INSERT INTO categories (name, color, sort_order, parent_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (parent_id, name) WHERE parent_id IS NOT NULL
            DO UPDATE SET parent_id = COALESCE(categories.parent_id, EXCLUDED.parent_id)
            RETURNING id
        """, (name, color, sort_order, parent_id))
    return cur.fetchone()[0]


def seed_country_categories() -> list[dict]:
    """各国×カテゴリ + マーケットセクションのデフォルトカテゴリを一括作成"""
    # (name, color, sort_order) - 第1・2階層
    COUNTRY_CATEGORIES = [
        # USA
        ("USA: 金融政策", "#1890ff", 1),
        ("USA: 経済", "#52c41a", 2),
        ("USA: 消費", "#13c2c2", 3),
        ("USA: 雇用", "#faad14", 4),
        ("USA: 物価", "#ff4d4f", 5),
        ("USA: 住宅", "#722ed1", 6),
        # Japan
        ("日本: 金融政策", "#1890ff", 10),
        ("日本: 経済", "#52c41a", 11),
        ("日本: 消費", "#13c2c2", 12),
        ("日本: 雇用", "#faad14", 13),
        ("日本: 物価", "#ff4d4f", 14),
        # Eurozone
        ("ユーロ圏: 金融政策", "#1890ff", 20),
        ("ユーロ圏: 経済", "#52c41a", 21),
        ("ユーロ圏: 消費", "#13c2c2", 22),
        ("ユーロ圏: 雇用", "#faad14", 23),
        ("ユーロ圏: 物価", "#ff4d4f", 24),
        # UK
        ("UK: 金融政策", "#1890ff", 30),
        ("UK: 経済", "#52c41a", 31),
        ("UK: 消費", "#13c2c2", 32),
        ("UK: 雇用", "#faad14", 33),
        ("UK: 物価", "#ff4d4f", 34),
        ("UK: 住宅", "#722ed1", 35),
        # China
        ("中国: 金融政策", "#1890ff", 40),
        ("中国: 経済", "#52c41a", 41),
        ("中国: 消費", "#13c2c2", 42),
        ("中国: 雇用", "#faad14", 43),
        ("中国: 物価", "#ff4d4f", 44),
        ("中国: 住宅", "#722ed1", 45),
        # Australia
        ("豪州: 金融政策", "#1890ff", 50),
        ("豪州: 経済", "#52c41a", 51),
        ("豪州: 消費", "#13c2c2", 52),
        ("豪州: 雇用", "#faad14", 53),
        ("豪州: 物価", "#ff4d4f", 54),
        ("豪州: 住宅", "#722ed1", 55),
        # New Zealand
        ("NZ: 金融政策", "#1890ff", 60),
        ("NZ: 経済", "#52c41a", 61),
        ("NZ: 消費", "#13c2c2", 62),
        ("NZ: 雇用", "#faad14", 63),
        ("NZ: 物価", "#ff4d4f", 64),
        # Canada
        ("カナダ: 金融政策", "#1890ff", 70),
        ("カナダ: 経済", "#52c41a", 71),
        ("カナダ: 消費", "#13c2c2", 72),
        ("カナダ: 雇用", "#faad14", 73),
        ("カナダ: 物価", "#ff4d4f", 74),
        ("カナダ: 住宅", "#722ed1", 75),
        # Switzerland
        ("スイス: 金融政策", "#1890ff", 80),
        ("スイス: 経済", "#52c41a", 81),
        ("スイス: 消費", "#13c2c2", 82),
        ("スイス: 雇用", "#faad14", 83),
        ("スイス: 物価", "#ff4d4f", 84),
        ("スイス: 住宅", "#722ed1", 85),
        # Global
        ("グローバル: 経済", "#52c41a", 90),
    ]

    # マーケットデータセクション（グローバル配下の子カテゴリ）
    MARKET_CHILDREN = [
        ("日本株", "#ef4444", 91),
        ("米国株", "#3b82f6", 92),
        ("欧州株", "#8b5cf6", 93),
        ("為替", "#06b6d4", 94),
        ("コモディティ", "#f59e0b", 95),
        ("エネルギー", "#ef4444", 96),
        ("債券/金利", "#10b981", 97),
        ("オプション", "#a855f7", 98),
    ]

    created = []
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 親ごとの一意制約を保証してから upsert（ON CONFLICT が部分インデックスを参照するため）
            _ensure_category_constraints(cur)
            # 第1・2階層
            for name, color, sort_order in COUNTRY_CATEGORIES:
                cat_id = _upsert_category(cur, name, color, sort_order)
                created.append({"id": cat_id, "name": name})

            # グローバル: 経済のIDを取得
            cur.execute("SELECT id FROM categories WHERE name = 'グローバル: 経済'")
            global_row = cur.fetchone()
            global_parent_id = global_row[0] if global_row else None

            # マーケットデータ子カテゴリ
            if global_parent_id:
                for name, color, sort_order in MARKET_CHILDREN:
                    cat_id = _upsert_category(cur, name, color, sort_order, global_parent_id)
                    created.append({"id": cat_id, "name": name, "parent_id": global_parent_id})

            conn.commit()
    return created


# ========== 既読マーカー「ここまで見た」(master 専用) ==========
# ヘッドラインは TTL_DAYS で削除されるため、headline_id ではなく
# marked_published_at(時刻ウォーターマーク)を真の状態として保持する。

def _ensure_read_marker_table(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS headline_read_marker (
            user_id INTEGER PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
            headline_id INTEGER,
            marked_published_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)


def get_read_marker(user_id: int) -> dict | None:
    """既読マーカーを取得 (未設定なら None)"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            _ensure_read_marker_table(cur)
            conn.commit()
            cur.execute("""
                SELECT headline_id, marked_published_at, updated_at
                FROM headline_read_marker WHERE user_id = %s
            """, (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "headline_id": row[0],
                "marked_published_at": row[1].isoformat() if row[1] else None,
                "updated_at": row[2].isoformat() if row[2] else None,
            }


def set_read_marker(user_id: int, headline_id: int) -> dict:
    """指定ヘッドラインの published_at を「ここまで見た」位置として保存"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            _ensure_read_marker_table(cur)
            cur.execute("SELECT published_at FROM headlines WHERE id = %s", (headline_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "Headline not found"}
            pub = row[0] or datetime.now(timezone.utc)
            cur.execute("""
                INSERT INTO headline_read_marker (user_id, headline_id, marked_published_at, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    headline_id = EXCLUDED.headline_id,
                    marked_published_at = EXCLUDED.marked_published_at,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, headline_id, pub))
            conn.commit()
            return {"headline_id": headline_id, "marked_published_at": pub.isoformat()}


def clear_read_marker(user_id: int) -> bool:
    """既読マーカーを解除"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            _ensure_read_marker_table(cur)
            cur.execute("DELETE FROM headline_read_marker WHERE user_id = %s", (user_id,))
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
