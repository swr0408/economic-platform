"""
法人企業景気予測調査 (BSI) の e-Stat ファイル取得 共通ヘルパー

bsi_service / bsi_comprehensive_service の両方が、e-Stat のファイル
(statInfId 付き Excel) を取得する。statInfId は四半期リリース毎に
ローテートし、旧 ID はやがて 404 になるため、Data Catalog API で
現行 ID を動的に解決する。両サービスでロジックが重複しないよう集約する。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

import requests

try:
    from backend.services.estat_catalog_service import get_estat_catalog_service
except ImportError:
    from services.estat_catalog_service import get_estat_catalog_service


# e-Stat ファイルダウンロードのベース URL
ESTAT_FILE_DOWNLOAD_URL = "https://www.e-stat.go.jp/stat-search/file-download"
# 法人企業景気予測調査の政府統計コード（財務省）
STATS_CODE = "00350610"
# Data Catalog で対象とするテーブル名（景気判断 BSI 本体。"計数項目" ではない）
TABLE_NAME_FILTER = "BSI項目"

# API 発見が失敗した場合に使う既知の statInfId（新しい順）。
# 動的解決が本筋で、これは保険（四半期更新でいずれ陳腐化し得る）。
FALLBACK_STAT_INF_IDS = (
    "000040462490",  # 2026-06-11 公表（BSI項目）
    "000040423305",  # 2026-03-12 公表
    "000040385509",  # 2025-12-11 公表
)


def resolve_stat_inf_ids() -> List[str]:
    """現行の BSI ファイル(statInfId)を e-Stat Data Catalog API で動的解決する。

    直近 ~15 ヶ月の公開分に絞って「BSI項目」テーブルを問い合わせ、新しい順の
    statInfId を返す。API 失敗時は既知のフォールバック ID を返す。
    """
    ids: List[str] = []
    try:
        catalog = get_estat_catalog_service()
        today = datetime.now()
        start = (today - timedelta(days=460)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        urls = catalog.get_excel_download_urls(
            survey_code=STATS_CODE,
            limit=50,
            table_name_filter=TABLE_NAME_FILTER,
            updated_date=f"{start}-{end}",
        )
        for url_info in urls:  # 公開日 降順
            sid = catalog.extract_stat_inf_id_from_url(url_info.get("url", ""))
            if sid and sid not in ids:
                ids.append(sid)
        if ids:
            print(f"BSI: discovered {len(ids)} statInfId(s) via e-Stat catalog: {ids[:3]}")
        else:
            print("BSI: no statInfId discovered via catalog API, using fallback list")
    except Exception as e:  # noqa: BLE001 - 発見失敗は握りつぶしてフォールバック
        print(f"BSI: catalog discovery failed ({e}), using fallback list")

    for fid in FALLBACK_STAT_INF_IDS:
        if fid not in ids:
            ids.append(fid)
    return ids


def download_bsi_excel(timeout: int = 30) -> bytes:
    """現行 statInfId を順に試し、最初に取得できた Excel の内容(bytes)を返す。"""
    last_error: Optional[str] = None
    for sid in resolve_stat_inf_ids():
        try:
            resp = requests.get(
                ESTAT_FILE_DOWNLOAD_URL,
                params={"statInfId": sid, "fileKind": "0"},
                timeout=timeout,
            )
            if resp.status_code == 200 and len(resp.content) > 1000:
                print(f"BSI: downloaded Excel via statInfId={sid} ({len(resp.content)} bytes)")
                return resp.content
            last_error = f"statInfId={sid} HTTP {resp.status_code}"
            print(f"BSI: {last_error}, trying next...")
        except Exception as e:  # noqa: BLE001
            last_error = f"statInfId={sid}: {e}"
            print(f"BSI: {last_error}, trying next...")
    raise RuntimeError(f"BSI: failed to download Excel from e-Stat. Last error: {last_error}")
