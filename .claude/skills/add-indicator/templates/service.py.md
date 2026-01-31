# サービスファイルテンプレート

以下のテンプレートを使用してサービスファイルを作成してください。
`{変数}` の部分を入力フォームの値で置き換えてください。

---

## ファイルパス

```
backend/services/{country}/{snake_case}_service.py
```

---

## テンプレートコード

```python
"""
{indicator_name_ja}サービス
{data_source_name}から{indicator_name_en}データを取得

指標:
- {indicator_name_en}（{indicator_name_ja}）

データソース:
- {data_source_name}
- {data_source_url}

発表スケジュール:
- {release_pattern}

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.{country}.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "{country}" / "{category}"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "{snake_case}_cache.json"


class {pascal_case}Service:
    """{indicator_name_ja}サービス"""

    DATA_CACHE_KEY = "{country}:{snake_case}:data"
    ECONALPHA_ID = "{econalpha_id}"
    FMP_COUNTRY = "{fmp_country}"
    FMP_EVENT_PATTERN = "{fmp_event_pattern}"

    # データソースURL
    DATA_SOURCE_URL = "{data_source_url}"

    def __init__(self):
        pass

    def get_{snake_case}_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """{indicator_name_ja}データを取得"""
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

        # データソースから取得
        result = self._load_from_source()
        if result:
            # 最新値を取得
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "{data_source_name}",
                    "indicator": "{indicator_name_en}",
                    "description": "{indicator_name_ja}",
                    "unit": "{unit}",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
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

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """データソースからデータを取得"""
        try:
            print(f"[{pascal_case}] Fetching data from: {self.DATA_SOURCE_URL}")

            # ===== データ取得処理をここに実装 =====
            #
            # API の場合:
            # resp = requests.get(self.DATA_SOURCE_URL, timeout=60)
            # resp.raise_for_status()
            # data = resp.json()
            #
            # Excel の場合:
            # resp = requests.get(self.DATA_SOURCE_URL, timeout=120)
            # resp.raise_for_status()
            # excel_data = io.BytesIO(resp.content)
            # xl = pd.ExcelFile(excel_data)
            #
            # ===== 実際の処理を記述 =====

            result = []

            # データを以下の形式に変換:
            # result.append({
            #     "date": "YYYY-MM-DD",  # 日付（月次の場合は月初日）
            #     "value": float_value,  # 値
            #     # 必要に応じて追加フィールド
            # })

            # 日付でソートして重複を除去
            result.sort(key=lambda x: x["date"])
            seen_dates = set()
            unique_result = []
            for item in result:
                if item["date"] not in seen_dates:
                    seen_dates.add(item["date"])
                    unique_result.append(item)

            print(f"[{pascal_case}] Loaded {len(unique_result)} records")
            if unique_result:
                print(f"[{pascal_case}] Date range: {unique_result[0]['date']} to {unique_result[-1]['date']}")
                print(f"[{pascal_case}] Latest: value={unique_result[-1].get('value')}")

            return unique_result

        except Exception as e:
            print(f"[{pascal_case}] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

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
            print(f"[{pascal_case}] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[{pascal_case}] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "{indicator_name_en}",
            "source": "{data_source_name}",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
{snake_case}_service = {pascal_case}Service()
```

---

## Excel複数シート対応の例

Excel で年ごとにシートが分かれている場合：

```python
def _load_from_source(self) -> List[Dict[str, Any]]:
    """BFS APIからデータを取得（全年度のシートから結合）"""
    try:
        print(f"[{pascal_case}] Fetching data from: {self.DATA_SOURCE_URL}")

        resp = requests.get(self.DATA_SOURCE_URL, timeout=120)
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

            # シートからデータを抽出する処理
            # ...

        # 日付でソートして重複を除去
        result.sort(key=lambda x: x["date"])
        seen_dates = set()
        unique_result = []
        for item in result:
            if item["date"] not in seen_dates:
                seen_dates.add(item["date"])
                unique_result.append(item)

        return unique_result

    except Exception as e:
        print(f"[{pascal_case}] Error loading data: {e}")
        return []
```

---

## DB から取得する場合の例

```python
def _load_from_db(self) -> List[Dict[str, Any]]:
    """DBから履歴データを取得"""
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            query = text("""
                SELECT datetime_utc, actual, estimate, previous
                FROM economic_calendar_events
                WHERE country = :country
                  AND event ILIKE :pattern
                  AND actual IS NOT NULL
                ORDER BY datetime_utc ASC
            """)
            rows = session.execute(query, {
                "country": self.FMP_COUNTRY,
                "pattern": f"%{self.FMP_EVENT_PATTERN}%"
            }).fetchall()

            result = []
            seen_dates = set()

            for row in rows:
                dt_utc, actual, estimate, previous = row
                if dt_utc:
                    date_str = dt_utc.strftime("%Y-%m-01")  # 月初日に正規化
                    if date_str in seen_dates:
                        continue
                    seen_dates.add(date_str)

                    result.append({
                        "date": date_str,
                        "value": float(actual) if actual else None,
                        "forecast": float(estimate) if estimate else None,
                        "previous": float(previous) if previous else None,
                    })

            print(f"[{pascal_case}] Loaded {len(result)} records from DB")
            return result

    except Exception as e:
        print(f"[{pascal_case}] Error loading from DB: {e}")
        return []
```
