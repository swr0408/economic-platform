"""
ヘッドライン正規化 + 重複判定キー生成
"""

import hashlib
import re
from html import unescape
from urllib.parse import urlparse, urlencode, parse_qs


def normalize_text(text: str) -> str:
    """テキストを正規化して重複判定用の文字列を返す"""
    if not text:
        return ""
    t = text.strip()
    t = unescape(t)
    # 連続空白を1個に
    t = re.sub(r'\s+', ' ', t)
    # 全角英数を半角に
    t = t.translate(str.maketrans(
        'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９',
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    ))
    # $MACRO 等の末尾タグを除去
    t = re.sub(r'\s*\$\w+\s*$', '', t)
    # 末尾URLを分離（正規化対象外にする）
    t = re.sub(r'\s*https?://\S+\s*$', '', t)
    return t.strip()


def normalize_url(url: str) -> str:
    """URLを正規化"""
    if not url:
        return ""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    host = parsed.hostname.lower() if parsed.hostname else ""
    path = parsed.path.rstrip('/')
    # utm_* 等のトラッキングパラメータを除去
    qs = parse_qs(parsed.query, keep_blank_values=False)
    filtered = {k: v for k, v in qs.items() if not k.startswith('utm_')}
    query = urlencode(filtered, doseq=True) if filtered else ""
    result = f"{scheme}://{host}{path}"
    if query:
        result += f"?{query}"
    return result


def text_hash(text: str) -> str:
    """正規化テキストのSHA256ハッシュ"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest() if text else ""


def generate_dedupe_key(
    guid: str = None,
    link: str = None,
    normalized_text: str = None,
    source_message_id: int = None,
    source_type: str = "discord",
) -> str:
    """重複判定キーを生成"""
    if source_type == "discord" and source_message_id:
        return f"discord:{source_message_id}"
    if guid:
        return f"guid:{guid}"
    if link:
        return f"link:{normalize_url(link)}"
    if normalized_text:
        return f"text:{text_hash(normalized_text)}"
    return ""


def time_bucket_5m(dt) -> str:
    """datetimeを5分単位に丸めた文字列を返す"""
    if dt is None:
        return ""
    minute = (dt.minute // 5) * 5
    return dt.replace(minute=minute, second=0, microsecond=0).isoformat()
