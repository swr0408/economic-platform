"""
スイス失業率サービス
BFS（スイス連邦統計局）から失業率データを取得

指標:
- Unemployment Rate（失業率）
- スイスの月次失業率データ

データソース:
- BFS（Federal Statistical Office）
- https://dam-api.bfs.admin.ch/hub/api/dam/assets/36341018/master

発表スケジュール:
- 毎月（FMPカレンダーから取得）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import io
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.switzerland.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_unemployment_rate_cache.json"


class CHUnemploymentRateService:
    """スイス失業率サービス"""

    DATA_CACHE_KEY = "switzerland:ch_unemployment_rate:data"
    ECONALPHA_ID = "ch_unemployment_rate"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERN = "Unemployment Rate"

    # BFS API: 公表ごとに damId が変わるため、シード ID から最新版を動的解決する
    # (orderNr ベース解決。詳細は bfs_asset_resolver.py)
    BFS_SEED_ASSET_ID = "36341018"
    BFS_API_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36341018/master"  # フォールバック

    def __init__(self):
        pass

    def get_unemployment_rate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイス失業率データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # BFS APIから取得
        bfs_result = self._load_from_bfs()
        if bfs_result:
            # BFS Excelは発表当日〜数日ラグするため、発表済みだが未反映の月を
            # FMP速報(n.s.a)で補完する。BFSが後日確報Excelを出したら次回発表時の
            # 再取得でそちらが優先される（補完はBFS最新月より後の月しか追記しない）
            bfs_latest_date = bfs_result[-1]["date"] if bfs_result else None
            bfs_result = self._supplement_from_fmp(bfs_result, bfs_latest_date)

            # 最新値を取得（補完後）
            latest = bfs_result[-1] if bfs_result else None

            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "data": bfs_result,
                "latest": latest,
                "metadata": {
                    "source": "BFS (Federal Statistical Office)",
                    "indicator": "Unemployment Rate",
                    "description": "スイス失業率",
                    "unit": "%",
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": bfs_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "bfs_api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_bfs(self) -> List[Dict[str, Any]]:
        """BFS APIからデータを取得（全年度のシートから結合）"""
        try:
            from services.switzerland.bfs_asset_resolver import resolve_master_url
            url = resolve_master_url(self.BFS_SEED_ASSET_ID)
            print(f"[CHUnemploymentRate] Fetching data from BFS API: {url}")

            resp = requests.get(url, timeout=120)
            resp.raise_for_status()

            excel_data = io.BytesIO(resp.content)
            xl = pd.ExcelFile(excel_data)

            result = []
            current_date = datetime.now(JST).date()

            # 各年のシートからデータを取得
            for sheet_name in xl.sheet_names:
                try:
                    year = int(sheet_name)
                except ValueError:
                    continue

                excel_data.seek(0)
                df = pd.read_excel(excel_data, sheet_name=sheet_name)

                # Totalの行を探す
                total_row = None
                for idx, row in df.iterrows():
                    first_col = row.iloc[0]
                    if isinstance(first_col, str) and first_col.strip() == 'Total':
                        total_row = row
                        break

                if total_row is None:
                    print(f"[CHUnemploymentRate] No Total row found in sheet {year}")
                    continue

                # ヘッダー行（月のカラム名が含まれる行）を探す
                header_row = None
                for idx, row in df.iterrows():
                    # カラム名に年-月形式が含まれる行を探す
                    for col_idx, val in enumerate(row):
                        if isinstance(val, str) and f"{year}-" in val:
                            header_row = row
                            break
                    if header_row is not None:
                        break

                if header_row is None:
                    print(f"[CHUnemploymentRate] No header row found in sheet {year}")
                    continue

                # 各月のデータを抽出
                for col_idx in range(2, len(df.columns)):
                    header_val = header_row.iloc[col_idx]
                    if pd.isna(header_val):
                        continue

                    header_str = str(header_val).strip()

                    # 年-月形式 (例: 2025-01)
                    if f"{year}-" in header_str:
                        # "2025-01" または "2025-01 3)" のような形式
                        date_part = header_str.split()[0]  # "2025-01 3)" -> "2025-01"
                        try:
                            month = int(date_part.split('-')[1])
                            date_formatted = f"{year}-{month:02d}-01"
                        except (IndexError, ValueError):
                            continue
                    else:
                        continue

                    # 未来のデータはスキップ
                    try:
                        date_obj = datetime.strptime(date_formatted, "%Y-%m-%d").date()
                        if date_obj > current_date:
                            continue
                    except ValueError:
                        continue

                    # Totalの値を取得
                    value = total_row.iloc[col_idx]
                    if pd.isna(value):
                        continue

                    try:
                        value_float = float(value)
                    except (ValueError, TypeError):
                        continue

                    result.append({
                        "date": date_formatted,
                        "value": round(value_float, 2),
                    })

            # 日付でソートして重複を除去
            result.sort(key=lambda x: x["date"])
            seen_dates = set()
            unique_result = []
            for item in result:
                if item["date"] not in seen_dates:
                    seen_dates.add(item["date"])
                    unique_result.append(item)

            print(f"[CHUnemploymentRate] Loaded {len(unique_result)} records from BFS API")
            if unique_result:
                print(f"[CHUnemploymentRate] Date range: {unique_result[0]['date']} to {unique_result[-1]['date']}")
                print(f"[CHUnemploymentRate] Latest: value={unique_result[-1].get('value')}%")

            return unique_result

        except Exception as e:
            print(f"[CHUnemploymentRate] Error loading from BFS API: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _supplement_from_fmp(
        self, bfs_data: List[Dict[str, Any]], bfs_latest_date: Optional[str]
    ) -> List[Dict[str, Any]]:
        """FMP（economic_calendar_events）の速報実値でBFS最新月より先の月を補完する。

        BFSのDAM Excel（orderNr je-d-03.03.02.05）はSECO記者発表（毎月上旬）から数日
        遅れて更新されるため、発表済みの当月がしばらく反映されない。FMPは同じSECO登録
        失業率を当月発表として持つ（イベント例: "Unemployment Rate n.s.a (Jun)" actual=2.9）。
        BFSの「Total」は季節調整なし系列なので、必ず n.s.a イベントを使う（季節調整版を
        混ぜると系列の季節形状が壊れる）。BFS最新月より後の月だけを追記し、BFSが後日
        確報を出せば次回取得でそちらが優先される（同月は追記しない）。
        """
        if not bfs_data or not bfs_latest_date:
            return bfs_data
        try:
            existing = {d["date"] for d in bfs_data}

            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                rows = session.execute(
                    text("""
                        SELECT datetime_utc, event, actual
                        FROM economic_calendar_events
                        WHERE country = 'CH'
                          AND event ILIKE '%Unemployment Rate n.s.a%'
                          AND actual IS NOT NULL
                          AND datetime_utc >= NOW() - INTERVAL '120 days'
                        ORDER BY datetime_utc ASC
                    """)
                ).fetchall()

            # ref月(YYYY-MM-01) → 値（同一refは後勝ち=改定値優先）
            by_month: Dict[str, float] = {}
            for dt_utc, event, actual in rows:
                ref = self._parse_ref_month(event, dt_utc)
                if ref and actual is not None:
                    by_month[ref] = round(float(actual), 2)

            added = []
            for ref, val in by_month.items():
                if ref not in existing and ref > bfs_latest_date:
                    bfs_data.append({"date": ref, "value": val})
                    added.append(ref)

            if added:
                bfs_data.sort(key=lambda x: x["date"])
                print(f"[CHUnemploymentRate] FMP flash supplement added: {added}")

            return bfs_data
        except Exception as e:
            print(f"[CHUnemploymentRate] FMP supplement error: {e}")
            return bfs_data

    @staticmethod
    def _parse_ref_month(label: str, release_dt: datetime) -> Optional[str]:
        """イベントラベルの "(Jun)" 等から参照月 "YYYY-MM-01" を復元。

        スイス失業率は前月分を翌月上旬に発表（"(Jun)" は7月上旬発表=6月分）。
        ラベル月が発表月より先行している場合（"(Dec)" を1月発表）は前年と判定する。
        """
        m = re.search(r"\(([A-Za-z]{3})\)", label or "")
        if not m:
            return None
        mon = _MONTH_ABBR.get(m.group(1).lower())
        if not mon:
            return None
        year = release_dt.year
        if mon > release_dt.month + 1:
            year -= 1
        return f"{year:04d}-{mon:02d}-01"

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CHUnemploymentRate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHUnemploymentRate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "CH Unemployment Rate",
            "source": "BFS (Federal Statistical Office)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_unemployment_rate_service = CHUnemploymentRateService()
