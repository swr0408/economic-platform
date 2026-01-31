# ダッシュボードローダーテンプレート

ダッシュボードローダーの更新方法を説明します。

---

## ファイルパス

```
backend/services/dashboard/loaders/{country}_{category}.py
```

---

## 既存ローダーへの追加手順

### 1. EXPECTED_KEYS に追加

```python
class {Country}{Category}Loader(BaseDashboardLoader):
    """
    {country}{category}ダッシュボード用データローダー
    """

    COUNTRY_CODE = "{country}"
    CATEGORY_CODE = "{category}"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        # ... 既存のキー ...
        "{snake_case}",  # ← 追加
    ]
```

### 2. load_all() に取得処理を追加

```python
def load_all(self) -> Dict[str, Any]:
    """
    全データを並列で取得
    """
    # 遅延インポート（循環参照回避）
    from services.{country}.{snake_case}_service import {snake_case}_service
    # ... 他のインポート ...

    result = {
        # ... 既存のキー ...
        "{snake_case}": None,  # ← 追加
    }

    # 並列でデータを取得
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            # ... 既存のfutures ...
            executor.submit(self._get_{snake_case}, {snake_case}_service): "{snake_case}",  # ← 追加
        }

        for future in as_completed(futures):
            key = futures[future]
            try:
                result[key] = future.result()
            except Exception as e:
                print(f"[{Country}{Category}] Error fetching {key}: {e}")
                result[key] = None

    return result
```

### 3. ヘルパーメソッドを追加

```python
def _get_{snake_case}(self, service) -> dict:
    """{indicator_name_ja}データを取得"""
    try:
        force_refresh = self._should_force_refresh("{snake_case}")
        response = service.get_{snake_case}_data(force_refresh=force_refresh)
        return {
            "data": response.get("data", []),
            "latest": response.get("latest"),
            "metadata": response.get("metadata", {}),
            "next_release": response.get("next_release"),
        }
    except Exception as e:
        print(f"[{Country}{Category}] Error getting {indicator_name_ja}: {e}")
        return {"data": [], "latest": None, "metadata": {}, "next_release": None}
```

---

## 新規ローダー作成時のテンプレート

新しいカテゴリのローダーを作成する場合：

```python
"""
{country}{category}ダッシュボードローダー
{指標リスト}を一括取得

キャッシュ更新判定: FMP発表日時ベース判定
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard.loaders.base import BaseDashboardLoader


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class {Country}{Category}Loader(BaseDashboardLoader):
    """
    {country}{category}ダッシュボード用データローダー

    取得データ:
    - {snake_case}: {indicator_name_ja}

    キャッシュ方式: FMP発表日時ベース判定
    """

    COUNTRY_CODE = "{country}"
    CATEGORY_CODE = "{category}"

    # 期待されるデータキー
    EXPECTED_KEYS = [
        "{snake_case}",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        """期待されるデータキーのリストを返す"""
        return self.EXPECTED_KEYS

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """各指標の発表日時リストを返す"""
        return []

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """発表日時を過ぎた指標を検出"""
        stale = set()

        if last_updated is None:
            return {"all"}

        return stale

    def _should_force_refresh(self, indicator: str) -> bool:
        """指標が強制更新対象かどうかを判定"""
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """データ再取得の前処理"""
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"[{Country}{Category}] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        """
        全データを並列で取得

        Returns:
            {
                "{snake_case}": {...},
            }
        """
        # 遅延インポート（循環参照回避）
        from services.{country}.{snake_case}_service import {snake_case}_service

        result = {
            "{snake_case}": None,
        }

        # 並列でデータを取得
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {
                executor.submit(self._get_{snake_case}, {snake_case}_service): "{snake_case}",
            }

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result[key] = future.result()
                except Exception as e:
                    print(f"[{Country}{Category}] Error fetching {key}: {e}")
                    result[key] = None

        return result

    def _get_{snake_case}(self, service) -> dict:
        """{indicator_name_ja}データを取得"""
        try:
            force_refresh = self._should_force_refresh("{snake_case}")
            response = service.get_{snake_case}_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[{Country}{Category}] Error getting {indicator_name_ja}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
```

---

## レジストリへの登録確認

`backend/services/dashboard/registry.py` でローダーが登録されていることを確認：

```python
from services.dashboard.loaders.{country}_{category} import {Country}{Category}Loader

DASHBOARD_LOADERS = {
    # ... 既存のローダー ...
    ("{country}", "{category}"): {Country}{Category}Loader,
}
```
