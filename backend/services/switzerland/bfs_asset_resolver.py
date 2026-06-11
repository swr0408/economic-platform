# -*- coding: utf-8 -*-
"""
BFS (スイス連邦統計局) DAM 資産 ID 動的解決ヘルパー

問題:
  BFS は毎回の公表ごとにデータファイルを *新しい damId* で公開する
  (例: CPI/PPI/失業/鉱工業/小売)。サービスが `dam/assets/{ID}/master` の
  ID をハードコードしていると、次の公表で古いスナップショットに固定され
  データが凍結する (silent staleness)。

解決:
  各資産は安定したカタログ番号 `shop.orderNr` を持つ。
  `GET /hub/api/dam/assets?orderNr=<orderNr>` は同一データセットの
  最新版を返す。既存のハードコード ID を「シード」として渡すと、
  そのシードの orderNr を引き当て、最新 embargo の damId に解決した
  master URL を返す。解決に失敗したらシード ID の URL にフォールバック。

これによりサービス側は最小改修で、以後の公表でも自動追従できる。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

_DAM_BASE = "https://dam-api.bfs.admin.ch/hub/api/dam"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

# プロセス内キャッシュ: seed_id -> (resolved_url, ts)
_CACHE: Dict[str, Tuple[str, float]] = {}
_CACHE_TTL = 6 * 3600  # 6時間


def _master_url(asset_id: str | int) -> str:
    return f"{_DAM_BASE}/assets/{asset_id}/master"


def _order_nr_of(asset_id: str | int) -> Optional[str]:
    try:
        r = requests.get(f"{_DAM_BASE}/assets/{asset_id}", headers=_HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        return (r.json().get("shop") or {}).get("orderNr")
    except Exception as e:
        logger.warning(f"[BFSResolver] order_nr lookup failed for {asset_id}: {e}")
        return None


def _latest_damid_for_order(order_nr: str) -> Optional[str]:
    try:
        r = requests.get(f"{_DAM_BASE}/assets", params={"orderNr": order_nr},
                         headers=_HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        rows = r.json().get("data", []) or []
        # CURRENT ライフサイクルのみ、embargo 降順で最新
        cur = [d for d in rows
               if (d.get("bfs") or {}).get("lifecycleGroup") == "CURRENT"] or rows
        cur.sort(key=lambda d: (d.get("bfs") or {}).get("embargo", ""), reverse=True)
        if not cur:
            return None
        return str(cur[0]["ids"]["damId"])
    except Exception as e:
        logger.warning(f"[BFSResolver] orderNr resolve failed for {order_nr}: {e}")
        return None


def resolve_master_url(seed_asset_id: str | int) -> str:
    """シード damId から、同一データセットの最新版 master URL を返す。

    解決できない場合はシード ID の master URL をそのまま返す (フォールバック)。
    結果は 6 時間プロセス内キャッシュする。
    """
    seed = str(seed_asset_id)
    now = time.time()
    hit = _CACHE.get(seed)
    if hit and (now - hit[1]) < _CACHE_TTL:
        return hit[0]

    url = _master_url(seed)  # fallback default
    order_nr = _order_nr_of(seed)
    if order_nr:
        latest = _latest_damid_for_order(order_nr)
        if latest:
            url = _master_url(latest)
            if latest != seed:
                logger.info(
                    f"[BFSResolver] {seed} -> {latest} (orderNr={order_nr})"
                )
    _CACHE[seed] = (url, now)
    return url


def resolve_master_url_from_url(master_url: str) -> str:
    """`.../dam/assets/{ID}/master` URL からシード ID を抽出して最新版に解決する。

    既存サービスは URL 定数をそのまま `requests.get(url)` に渡しているため、
    その呼び出しを `requests.get(resolve_master_url_from_url(url))` に置き換える
    だけで動的追従にできる。抽出できない URL はそのまま返す。
    """
    import re
    m = re.search(r"/assets/(\d+)/master", master_url or "")
    if not m:
        return master_url
    return resolve_master_url(m.group(1))
