"""
FRED サービス共通ユーティリティ

各 FRED サービスで重複している処理を共通化:
- FRED API呼び出し
- キャッシュ管理（Redis + ファイル）
- 前月比・前年比計算
- スケジュール判定

使用例:
    from services.usa.fred_utils import (
        fetch_fred_series,
        calculate_changes,
        load_file_cache,
        save_file_cache,
        CacheManager,
    )
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# FRED API設定
FRED_BASE_URL = "https://api.stlouisfed.org/fred"
DEFAULT_START_DATE = "2000-01-01"


# =============================================================================
# FRED API呼び出し
# =============================================================================

def fetch_fred_series(
    series_id: str,
    start_date: Optional[str] = None,
    api_key: Optional[str] = None,
    round_digits: int = 2
) -> List[Dict[str, Any]]:
    """
    FRED APIから単一シリーズデータを取得

    Args:
        series_id: FREDシリーズID（例: "PCE", "ICSA"）
        start_date: 開始日（YYYY-MM-DD）、デフォルト2000-01-01
        api_key: FRED APIキー、Noneの場合は環境変数から取得
        round_digits: 値の丸め桁数

    Returns:
        [{"date": "YYYY-MM-DD", "value": float}, ...]
    """
    try:
        if not api_key:
            api_key = os.environ.get("FRED_API_KEY", "")

        if not api_key:
            print("FRED_API_KEY not set")
            return []

        if not start_date:
            start_date = DEFAULT_START_DATE

        url = f"{FRED_BASE_URL}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start_date,
            "sort_order": "asc"
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        observations = data.get("observations", [])

        result = []
        for obs in observations:
            try:
                value_str = obs.get("value", "")
                if value_str == "." or not value_str:
                    continue
                value = float(value_str)
                result.append({
                    "date": obs["date"],
                    "value": round(value, round_digits) if round_digits else value
                })
            except (ValueError, KeyError):
                continue

        return result

    except Exception as e:
        print(f"Error fetching FRED series {series_id}: {e}")
        return []


def fetch_multiple_fred_series(
    series_ids: List[str],
    start_date: Optional[str] = None,
    api_key: Optional[str] = None,
    round_digits: int = 2
) -> Dict[str, List[Dict[str, Any]]]:
    """
    FRED APIから複数シリーズデータを取得

    Args:
        series_ids: FREDシリーズIDのリスト
        start_date: 開始日
        api_key: FRED APIキー
        round_digits: 値の丸め桁数

    Returns:
        {"series_id": [{"date": "YYYY-MM-DD", "value": float}, ...], ...}
    """
    result = {}
    for series_id in series_ids:
        result[series_id] = fetch_fred_series(
            series_id, start_date, api_key, round_digits
        )
    return result


# =============================================================================
# 変化率計算
# =============================================================================

def calculate_changes(
    raw_data: List[Dict[str, Any]],
    include_value: bool = False,
    mom_offset: int = 1,
    yoy_offset: int = 12
) -> List[Dict[str, Any]]:
    """
    前期比・前年比を計算

    Args:
        raw_data: [{"date": str, "value": float}, ...]
        include_value: 結果にvalueを含めるか
        mom_offset: 前期比のオフセット（月次=1、四半期=1）
        yoy_offset: 前年比のオフセット（月次=12、四半期=4）

    Returns:
        [{"date": str, "mom": float|None, "yoy": float|None, ("value": float)}, ...]
    """
    result = []
    for i, item in enumerate(raw_data):
        entry = {
            "date": item["date"],
            "mom": None,
            "yoy": None,
        }

        if include_value:
            entry["value"] = item["value"]

        # 前期比（%）
        if i >= mom_offset:
            prev_value = raw_data[i - mom_offset]["value"]
            if prev_value and prev_value != 0:
                entry["mom"] = round((item["value"] / prev_value - 1) * 100, 2)

        # 前年比（%）
        if i >= yoy_offset:
            year_ago_value = raw_data[i - yoy_offset]["value"]
            if year_ago_value and year_ago_value != 0:
                entry["yoy"] = round((item["value"] / year_ago_value - 1) * 100, 2)

        result.append(entry)

    return result


def calculate_diff_changes(
    raw_data: List[Dict[str, Any]],
    include_value: bool = True,
    mom_offset: int = 1,
    yoy_offset: int = 12
) -> List[Dict[str, Any]]:
    """
    前期差・前年差を計算（変化「率」ではなく変化「量」）

    Args:
        raw_data: [{"date": str, "value": float}, ...]
        include_value: 結果にvalueを含めるか
        mom_offset: 前期差のオフセット
        yoy_offset: 前年差のオフセット

    Returns:
        [{"date": str, "value": float, "mom": float|None, "yoy": float|None}, ...]
    """
    result = []
    for i, item in enumerate(raw_data):
        entry = {
            "date": item["date"],
            "mom": None,
            "yoy": None,
        }

        if include_value:
            entry["value"] = item["value"]

        # 前期差
        if i >= mom_offset:
            prev_value = raw_data[i - mom_offset]["value"]
            if prev_value is not None:
                entry["mom"] = round(item["value"] - prev_value, 2)

        # 前年差
        if i >= yoy_offset:
            year_ago_value = raw_data[i - yoy_offset]["value"]
            if year_ago_value is not None:
                entry["yoy"] = round(item["value"] - year_ago_value, 2)

        result.append(entry)

    return result


def aggregate_weekly_to_monthly(
    raw_data: List[Dict[str, Any]],
    round_digits: int = 2
) -> List[Dict[str, Any]]:
    """
    週次データを月次データに集計（月平均）

    Args:
        raw_data: [{"date": "YYYY-MM-DD", "value": float}, ...]
        round_digits: 平均値の丸め桁数

    Returns:
        [{"date": "YYYY-MM-01", "value": float}, ...]
    """
    from collections import defaultdict

    # 月別にグループ化
    monthly_values: Dict[str, List[float]] = defaultdict(list)

    for item in raw_data:
        date_str = item["date"]
        value = item["value"]

        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            month_key = dt.strftime("%Y-%m")
            monthly_values[month_key].append(value)
        except ValueError:
            continue

    # 月平均を計算
    result = []
    for month_key in sorted(monthly_values.keys()):
        values = monthly_values[month_key]
        avg_value = sum(values) / len(values)
        result.append({
            "date": f"{month_key}-01",
            "value": round(avg_value, round_digits)
        })

    return result


# =============================================================================
# キャッシュ管理
# =============================================================================

def load_file_cache(cache_file: Path) -> Optional[Dict[str, Any]]:
    """
    ファイルキャッシュを読み込み

    Args:
        cache_file: キャッシュファイルのパス

    Returns:
        キャッシュデータまたはNone
    """
    try:
        if not cache_file.exists():
            return None
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load file cache {cache_file}: {e}")
        return None


def save_file_cache(cache_file: Path, data: Dict[str, Any]) -> bool:
    """
    ファイルキャッシュを保存

    Args:
        cache_file: キャッシュファイルのパス
        data: 保存するデータ

    Returns:
        成功したかどうか
    """
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Cache saved to {cache_file}")
        return True
    except Exception as e:
        print(f"Failed to save file cache {cache_file}: {e}")
        return False


class CacheManager:
    """
    キャッシュ管理クラス

    Redis + ファイルの2層キャッシュを管理し、
    FMPスケジュールベースの更新判定を行う

    使用例:
        cache_manager = CacheManager(
            redis_key="fred:pce:data",
            cache_file=Path("cache/usa/consumer/pce_cache.json"),
            econalpha_id="pce_mom"
        )

        # キャッシュチェック
        cached_data, source = cache_manager.get_cached_data()
        if cached_data:
            return cached_data

        # 新規データを保存
        cache_manager.save(new_data)
    """

    def __init__(
        self,
        redis_key: str,
        cache_file: Optional[Path] = None,
        econalpha_id: Optional[str] = None
    ):
        self.redis_key = redis_key
        self.cache_file = cache_file
        self.econalpha_id = econalpha_id

    def should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定

        FMPスケジュールベースで判定。FMPマッピングがない場合は
        TTLフォールバック（24時間）で定期的に更新を試みる。
        週次フォールバック（7日）: FMPスケジュールに関係なく最低週1回更新。
        """
        if self.econalpha_id:
            result = should_refresh_by_fmp_schedule(self.econalpha_id, last_updated_str)
            if result:
                return True
        # FMPマッピングがない場合やFMPで判定不可の場合、TTLフォールバック（24時間）
        # FMPマッピングがある場合でも最低週1回は強制更新（FMPスケジュール漏れ対策）
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            elapsed = (datetime.now(ZoneInfo("Asia/Tokyo")) - last_updated).total_seconds()
            if not self.econalpha_id and elapsed > 24 * 60 * 60:  # FMPマッピングなし: 24時間
                return True
            if elapsed > 7 * 24 * 60 * 60:  # FMPマッピングあり/なし共通: 7日以上経過で強制更新
                return True
        except Exception:
            pass
        return False

    def get_cached_data(self, force_refresh: bool = False) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        キャッシュされたデータを取得

        Args:
            force_refresh: キャッシュを無視するか

        Returns:
            (キャッシュデータ, ソース) - ソースは "redis", "file", または ""
        """
        if force_refresh:
            return None, ""

        # Redisキャッシュチェック
        cached_data = redis_client.get(self.redis_key)
        if cached_data:
            last_updated_str = cached_data.get("last_updated")
            if last_updated_str and not self.should_refresh(last_updated_str):
                return cached_data, "redis"

        # ファイルキャッシュチェック
        if self.cache_file:
            file_cache = load_file_cache(self.cache_file)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self.should_refresh(last_updated_str):
                    # Redisにも保存
                    redis_client.set(self.redis_key, file_cache, expire=0)
                    return file_cache, "file"

        return None, ""

    def get_fallback_data(self) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        フォールバック用のキャッシュデータを取得（更新判定なし）

        Returns:
            (キャッシュデータ, ソース)
        """
        if self.cache_file:
            file_cache = load_file_cache(self.cache_file)
            if file_cache:
                return file_cache, "file (fallback)"
        return None, ""

    def save(self, data: Dict[str, Any]) -> None:
        """
        データをキャッシュに保存

        Args:
            data: 保存するデータ（last_updatedは自動付与）
        """
        if "last_updated" not in data:
            data["last_updated"] = datetime.now(JST).isoformat()

        # Redisに保存
        redis_client.set(self.redis_key, data, expire=0)

        # ファイルにも保存
        if self.cache_file:
            save_file_cache(self.cache_file, data)

    def invalidate(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.redis_key)

    def exists(self) -> bool:
        """キャッシュが存在するか"""
        return redis_client.exists(self.redis_key)

    def get_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        exists = self.exists()
        cached_data = redis_client.get(self.redis_key) if exists else None

        return {
            "cache_key": self.redis_key,
            "exists": exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.econalpha_id) if self.econalpha_id else None,
            "file_cache_exists": self.cache_file.exists() if self.cache_file else False
        }


# =============================================================================
# レスポンスビルダー
# =============================================================================

def build_nominal_real_response(
    nominal_data: Optional[Dict[str, Any]],
    real_data: Optional[Dict[str, Any]],
    cached: bool,
    source: str,
    last_updated: Optional[str],
    econalpha_id: Optional[str] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    名目・実質データ用のレスポンスを構築

    Args:
        nominal_data: {"data": [...], "latest": {...}}
        real_data: {"data": [...], "latest": {...}}
        cached: キャッシュから取得したか
        source: データソース
        last_updated: 最終更新日時
        econalpha_id: FMPマッピングID
        error: エラーメッセージ

    Returns:
        統一されたAPIレスポンス形式
    """
    response = {
        "nominal": nominal_data,
        "real": real_data,
        "next_release": get_next_release_from_fmp(econalpha_id) if econalpha_id else None,
        "cached": cached,
        "source": source,
        "last_updated": last_updated
    }
    if error:
        response["error"] = error
    return response


def build_single_series_response(
    data: List[Dict[str, Any]],
    cached: bool,
    source: str,
    last_updated: Optional[str],
    econalpha_id: Optional[str] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    単一シリーズデータ用のレスポンスを構築

    Args:
        data: データリスト
        cached: キャッシュから取得したか
        source: データソース
        last_updated: 最終更新日時
        econalpha_id: FMPマッピングID
        error: エラーメッセージ

    Returns:
        統一されたAPIレスポンス形式
    """
    latest = data[-1] if data else None

    response = {
        "data": data,
        "latest": latest,
        "next_release": get_next_release_from_fmp(econalpha_id) if econalpha_id else None,
        "cached": cached,
        "source": source,
        "last_updated": last_updated
    }
    if error:
        response["error"] = error
    return response


# =============================================================================
# 単一シリーズサービス基底クラス
# =============================================================================

class BaseSingleSeriesService:
    """
    単一FREDシリーズサービスの基底クラス

    継承時に設定が必要:
    - SERIES_ID: FREDシリーズID（例: "PSAVERT"）
    - REDIS_KEY: Redisキャッシュキー（例: "fred:personal_saving_rate:data"）
    - ECONALPHA_ID: FMPマッピングID（例: "personal_saving_rate"）
    - CACHE_FILE: キャッシュファイルパス
    - INDICATOR_NAME: 指標名（ログ用）

    オーバーライド可能:
    - _process_data(): データ加工処理（デフォルトはcalculate_diff_changes）
    - _fetch_raw_data(): データ取得処理（週次→月次集計などの特殊処理用）

    使用例:
        class PersonalSavingRateService(BaseSingleSeriesService):
            SERIES_ID = "PSAVERT"
            REDIS_KEY = "fred:personal_saving_rate:data"
            ECONALPHA_ID = "personal_saving_rate"
            CACHE_FILE = CACHE_DIR / "personal_saving_rate_cache.json"
            INDICATOR_NAME = "Personal Saving Rate"

        service = PersonalSavingRateService()
        data = service.get_data()
    """

    # サブクラスで設定必須
    SERIES_ID: str = ""
    REDIS_KEY: str = ""
    ECONALPHA_ID: str = ""
    CACHE_FILE: Optional[Path] = None
    INDICATOR_NAME: str = ""

    # オプション設定
    DEFAULT_START_DATE: str = "2000-01-01"
    VALUE_ROUND_DIGITS: int = 2
    USE_DIFF_CHANGES: bool = True  # True: 差分計算、False: 変化率計算
    SKIP_CHANGES: bool = False  # True: 変化率計算をスキップ（水準値のみ）

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self._cache_manager = CacheManager(
            redis_key=self.REDIS_KEY,
            cache_file=self.CACHE_FILE,
            econalpha_id=self.ECONALPHA_ID
        )

    def get_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        データを取得（キャッシュ優先）

        Args:
            start_date: 開始日（YYYY-MM-DD）
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        # 1. キャッシュチェック
        cached_data, source = self._cache_manager.get_cached_data(force_refresh)
        if cached_data:
            return build_single_series_response(
                data=cached_data.get("data", []),
                cached=True,
                source=source,
                last_updated=cached_data.get("last_updated"),
                econalpha_id=self.ECONALPHA_ID
            )

        # 2. APIから取得
        api_data = self._fetch_and_process(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None
            now_str = datetime.now(JST).isoformat()

            # 発表レース対策（ラグガード）:
            # FREDが発表直後の未伝播などで最新月を含まない古いデータを返した場合、
            # last_updated を前回の値のまま維持する。これにより should_refresh が
            # 「発表消化済み」と誤判定して次回発表まで凍結するのを防ぎ、次回リクエストで
            # 再度FREDへ問い合わせて最新月を自己回復させる。
            # （BaseMultiSeriesService と同じロジック）
            existing_cache = redis_client.get(self.REDIS_KEY)
            existing_latest_date = None
            if existing_cache and existing_cache.get("latest"):
                existing_latest_date = existing_cache["latest"].get("date")

            new_latest_date = latest.get("date") if latest else None

            if existing_latest_date and new_latest_date and new_latest_date <= existing_latest_date:
                # APIデータがキャッシュより新しくない → last_updatedを維持
                # （データ自体は既存値の改定反映のため更新する）
                last_updated = existing_cache.get("last_updated", now_str)
                print(f"  {self.INDICATOR_NAME}: FRED data not newer (latest={new_latest_date}), keeping last_updated={last_updated}")
            else:
                last_updated = now_str

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": last_updated
            }
            self._cache_manager.save(cache_payload)

            return build_single_series_response(
                data=api_data,
                cached=False,
                source="api",
                last_updated=cache_payload["last_updated"],
                econalpha_id=self.ECONALPHA_ID
            )

        # 3. フォールバック
        fallback_data, fallback_source = self._cache_manager.get_fallback_data()
        if fallback_data:
            return build_single_series_response(
                data=fallback_data.get("data", []),
                cached=True,
                source=fallback_source,
                last_updated=fallback_data.get("last_updated"),
                econalpha_id=self.ECONALPHA_ID
            )

        return build_single_series_response(
            data=[],
            cached=False,
            source="none",
            last_updated=None,
            econalpha_id=self.ECONALPHA_ID,
            error="No data available"
        )

    def _fetch_and_process(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """データを取得して加工"""
        print(f"Fetching {self.INDICATOR_NAME} from FRED...")

        raw_data = self._fetch_raw_data(start_date)
        if not raw_data:
            return []

        processed = self._process_data(raw_data)
        print(f"Fetched {len(processed)} {self.INDICATOR_NAME} records")
        return processed

    def _fetch_raw_data(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        FRED APIから生データを取得（サブクラスでオーバーライド可能）

        週次→月次集計などの特殊処理が必要な場合はオーバーライドする
        """
        return fetch_fred_series(
            series_id=self.SERIES_ID,
            start_date=start_date or self.DEFAULT_START_DATE,
            api_key=self.api_key,
            round_digits=self.VALUE_ROUND_DIGITS
        )

    def _process_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        データを加工（サブクラスでオーバーライド可能）

        デフォルトは差分計算（貯蓄率などのポイントデータ向け）
        """
        if self.SKIP_CHANGES:
            # 変化率計算なし（水準値のみ）
            return raw_data
        elif self.USE_DIFF_CHANGES:
            return calculate_diff_changes(raw_data, include_value=True)
        else:
            return calculate_changes(raw_data, include_value=True)

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return self._cache_manager.invalidate()

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        status = self._cache_manager.get_status()
        status.update({
            "indicator": self.INDICATOR_NAME,
            "series_id": self.SERIES_ID,
        })
        cached_data = redis_client.get(self.REDIS_KEY) if status["exists"] else None
        if cached_data:
            status["data_count"] = len(cached_data.get("data", []))
            status["latest"] = cached_data.get("latest")
        return status


# =============================================================================
# 複数シリーズサービス基底クラス
# =============================================================================

class BaseMultiSeriesService:
    """
    複数FREDシリーズをマージするサービスの基底クラス

    継承時に設定が必要:
    - SERIES_CONFIG: シリーズ設定（{name: series_id, ...}）
    - REDIS_KEY: Redisキャッシュキー
    - ECONALPHA_ID: FMPマッピングID
    - CACHE_FILE: キャッシュファイルパス
    - INDICATOR_NAME: 指標名（ログ用）

    オーバーライド可能:
    - _merge_series_data(): シリーズデータのマージ処理
    - _process_merged_data(): マージ後のデータ加工（変化率計算など）
    - _fetch_series(): 個別シリーズの取得処理

    使用例:
        class UnemploymentRateService(BaseMultiSeriesService):
            SERIES_CONFIG = {
                "unrate": "UNRATE",
                "u6rate": "U6RATE"
            }
            REDIS_KEY = "fred:unemployment_rate:data"
            ECONALPHA_ID = "unemployment_rate"
            CACHE_FILE = CACHE_DIR / "unemployment_rate_cache.json"
            INDICATOR_NAME = "Unemployment Rate"
            PRIMARY_SERIES = "unrate"  # マージ時のベース

        service = UnemploymentRateService()
        data = service.get_data()
    """

    # サブクラスで設定必須
    SERIES_CONFIG: Dict[str, str] = {}  # {output_name: series_id}
    REDIS_KEY: str = ""
    ECONALPHA_ID: str = ""
    CACHE_FILE: Optional[Path] = None
    INDICATOR_NAME: str = ""

    # オプション設定
    DEFAULT_START_DATE: str = "2000-01-01"
    VALUE_ROUND_DIGITS: int = 2
    PRIMARY_SERIES: str = ""  # マージ時にベースとするシリーズ名
    CALCULATE_CHANGES: bool = False  # 変化率を計算するか
    USE_DIFF_CHANGES: bool = True  # True: 差分、False: 変化率

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self._cache_manager = CacheManager(
            redis_key=self.REDIS_KEY,
            cache_file=self.CACHE_FILE,
            econalpha_id=self.ECONALPHA_ID
        )

    def get_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        データを取得（キャッシュ優先）

        Args:
            start_date: 開始日（YYYY-MM-DD）
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
        """
        # 1. キャッシュチェック
        cached_data, source = self._cache_manager.get_cached_data(force_refresh)
        if cached_data:
            return build_single_series_response(
                data=cached_data.get("data", []),
                cached=True,
                source=source,
                last_updated=cached_data.get("last_updated"),
                econalpha_id=self.ECONALPHA_ID
            )

        # 2. APIから取得
        api_data = self._fetch_and_process(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None
            now_str = datetime.now(JST).isoformat()

            # FREDが更新遅延で古いデータを返した場合、last_updatedを更新しない
            # これにより次回リクエストで再度FREDに問い合わせる
            existing_cache = redis_client.get(self.REDIS_KEY)
            existing_latest_date = None
            if existing_cache and existing_cache.get("latest"):
                existing_latest_date = existing_cache["latest"].get("date")

            new_latest_date = latest.get("date") if latest else None

            if existing_latest_date and new_latest_date and new_latest_date <= existing_latest_date:
                # APIデータがキャッシュより新しくない場合、last_updatedを維持
                # ただしデータ自体は更新（既存値の修正がある可能性）
                old_last_updated = existing_cache.get("last_updated", now_str)
                cache_payload = {
                    "data": api_data,
                    "latest": latest,
                    "last_updated": old_last_updated
                }
                print(f"  {self.INDICATOR_NAME}: FRED data not newer (latest={new_latest_date}), keeping last_updated={old_last_updated}")
            else:
                cache_payload = {
                    "data": api_data,
                    "latest": latest,
                    "last_updated": now_str
                }

            self._cache_manager.save(cache_payload)

            return build_single_series_response(
                data=api_data,
                cached=False,
                source="api",
                last_updated=cache_payload["last_updated"],
                econalpha_id=self.ECONALPHA_ID
            )

        # 3. フォールバック
        fallback_data, fallback_source = self._cache_manager.get_fallback_data()
        if fallback_data:
            return build_single_series_response(
                data=fallback_data.get("data", []),
                cached=True,
                source=fallback_source,
                last_updated=fallback_data.get("last_updated"),
                econalpha_id=self.ECONALPHA_ID
            )

        return build_single_series_response(
            data=[],
            cached=False,
            source="none",
            last_updated=None,
            econalpha_id=self.ECONALPHA_ID,
            error="No data available"
        )

    def _fetch_and_process(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """全シリーズを取得してマージ・加工"""
        print(f"Fetching {self.INDICATOR_NAME} from FRED...")

        if not self.api_key:
            print("FRED_API_KEY not set")
            return []

        # 各シリーズを取得
        series_data: Dict[str, List[Dict[str, Any]]] = {}
        for name, series_id in self.SERIES_CONFIG.items():
            data = self._fetch_series(series_id, start_date)
            if data:
                series_data[name] = data
                print(f"  {name} ({series_id}): {len(data)} records")

        if not series_data:
            return []

        # PRIMARY_SERIESが設定されているのに取得失敗した場合、
        # 破損データ（valueフィールドが全てNone）を生成しないよう中断
        # Why: _merge_series_dataが代替シリーズをprimaryに使うと、PRIMARY_SERIESに
        # 対応するフィールドが全てNoneになり、ダッシュボードキャッシュに永続的に
        # 残ってしまうため
        if self.PRIMARY_SERIES and self.PRIMARY_SERIES not in series_data:
            print(
                f"  {self.INDICATOR_NAME}: PRIMARY_SERIES '{self.PRIMARY_SERIES}' "
                f"not fetched — aborting to preserve previous cache"
            )
            return []

        # シリーズをマージ
        merged = self._merge_series_data(series_data)

        # マージ後の加工（変化率計算など）
        processed = self._process_merged_data(merged)

        print(f"Fetched {len(processed)} {self.INDICATOR_NAME} records")
        return processed

    def _fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        個別シリーズを取得（サブクラスでオーバーライド可能）
        """
        return fetch_fred_series(
            series_id=series_id,
            start_date=start_date or self.DEFAULT_START_DATE,
            api_key=self.api_key,
            round_digits=self.VALUE_ROUND_DIGITS
        )

    def _merge_series_data(
        self,
        series_data: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        複数シリーズのデータを日付ごとにマージ（サブクラスでオーバーライド可能）

        デフォルト実装:
        - PRIMARY_SERIESをベースに他のシリーズをマージ
        - 各シリーズの値を対応するフィールド名で格納

        Args:
            series_data: {series_name: [{"date": str, "value": float}, ...], ...}

        Returns:
            [{"date": str, "series1": float, "series2": float, ...}, ...]
        """
        # プライマリシリーズを決定
        primary = self.PRIMARY_SERIES or list(self.SERIES_CONFIG.keys())[0]

        if primary not in series_data:
            # プライマリがない場合は最初の利用可能なシリーズを使用
            primary = next(iter(series_data.keys()))

        # 各シリーズを日付でインデックス化
        series_maps: Dict[str, Dict[str, float]] = {}
        for name, data in series_data.items():
            series_maps[name] = {item["date"]: item["value"] for item in data}

        # プライマリシリーズをベースにマージ
        result = []
        for item in series_data[primary]:
            entry = {"date": item["date"]}
            for name in self.SERIES_CONFIG.keys():
                if name in series_maps:
                    entry[name] = series_maps[name].get(item["date"])
                else:
                    entry[name] = None
            result.append(entry)

        return result

    def _process_merged_data(
        self,
        merged_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        マージ後のデータを加工（サブクラスでオーバーライド可能）

        デフォルト実装: 変化率計算なし（そのまま返す）
        """
        if not self.CALCULATE_CHANGES:
            return merged_data

        # 変化率計算が必要な場合
        primary = self.PRIMARY_SERIES or list(self.SERIES_CONFIG.keys())[0]

        for i, item in enumerate(merged_data):
            if i >= 1:
                prev = merged_data[i - 1]
                for name in self.SERIES_CONFIG.keys():
                    curr_val = item.get(name)
                    prev_val = prev.get(name)
                    if curr_val is not None and prev_val is not None and prev_val != 0:
                        if self.USE_DIFF_CHANGES:
                            item[f"{name}_mom"] = round(curr_val - prev_val, 2)
                        else:
                            item[f"{name}_mom"] = round((curr_val / prev_val - 1) * 100, 2)

            if i >= 12:
                year_ago = merged_data[i - 12]
                for name in self.SERIES_CONFIG.keys():
                    curr_val = item.get(name)
                    year_ago_val = year_ago.get(name)
                    if curr_val is not None and year_ago_val is not None and year_ago_val != 0:
                        if self.USE_DIFF_CHANGES:
                            item[f"{name}_yoy"] = round(curr_val - year_ago_val, 2)
                        else:
                            item[f"{name}_yoy"] = round((curr_val / year_ago_val - 1) * 100, 2)

        return merged_data

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return self._cache_manager.invalidate()

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        status = self._cache_manager.get_status()
        status.update({
            "indicator": self.INDICATOR_NAME,
            "series_ids": self.SERIES_CONFIG,
        })
        cached_data = redis_client.get(self.REDIS_KEY) if status["exists"] else None
        if cached_data:
            status["data_count"] = len(cached_data.get("data", []))
            status["latest"] = cached_data.get("latest")
        return status
