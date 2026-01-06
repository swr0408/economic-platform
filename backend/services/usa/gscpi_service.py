"""
グローバルサプライチェーン圧力指数（GSCPI）サービス
NY連銀のExcelファイルからGSCPIデータを取得

指標:
- GSCPI（Global Supply Chain Pressure Index）
- 輸送・製造業セクターのデータからグローバルサプライチェーンの状態を追跡
- 0がサプライチェーン圧力の平均値、正の値は圧力上昇を示す

データソース:
- NY連銀（Federal Reserve Bank of New York）
- https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx

発表スケジュール:
- 毎月第4営業日以降の午前10時頃（ET）

キャッシュ方式: 毎日3分方式（毎月第4営業日以降に更新確認）
"""
import json
import io
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import requests

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
GSCPI_CACHE_FILE = CACHE_DIR / "gscpi_cache.json"

# NY連銀のGSCPIデータダウンロードURL
GSCPI_DATA_URL = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"


class GSCPIService:
    """グローバルサプライチェーン圧力指数サービス"""

    DATA_CACHE_KEY = "inflation:gscpi:data"

    def __init__(self):
        pass

    def get_gscpi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        GSCPIデータを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            GSCPIデータと最新値
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # NY連銀からExcelファイルを取得
        excel_result = self._fetch_from_nyfed()
        if excel_result:
            latest = excel_result[-1] if excel_result else None
            next_release = self._get_next_release()

            cache_payload = {
                "data": excel_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": excel_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "nyfed",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_nyfed(self) -> List[Dict[str, Any]]:
        """NY連銀からGSCPIデータをExcelファイルで取得"""
        try:
            print(f"Fetching GSCPI data from NY Fed: {GSCPI_DATA_URL}")

            # Excelファイルをダウンロード
            response = requests.get(GSCPI_DATA_URL, timeout=30)
            response.raise_for_status()

            # ExcelファイルをDataFrameとして読み込み
            excel_data = pd.ExcelFile(io.BytesIO(response.content))
            print(f"Available sheets: {excel_data.sheet_names}")

            # GSCPI Monthly Data シートを読み込み（ヘッダーなし、データは5行目から）
            gscpi_df = pd.read_excel(
                excel_data,
                sheet_name='GSCPI Monthly Data',
                header=None,
                skiprows=5
            )
            print(f"GSCPI data shape: {gscpi_df.shape}")

            # 列名を設定（Date, GSCPI, その他）
            if gscpi_df.shape[1] >= 2:
                gscpi_df.columns = ['Date', 'GSCPI'] + [f'Col{i}' for i in range(2, gscpi_df.shape[1])]

            # データを処理
            result = self._process_gscpi_data(gscpi_df)

            print(f"Loaded {len(result)} GSCPI records from NY Fed")
            return result

        except Exception as e:
            print(f"Error fetching GSCPI from NY Fed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _process_gscpi_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        GSCPIデータを処理してAPI用フォーマットに変換

        Args:
            df: データフレーム

        Returns:
            API用フォーマットのデータ
        """
        try:
            if 'Date' not in df.columns or 'GSCPI' not in df.columns:
                print(f"Required columns not found. Available columns: {list(df.columns)}")
                return []

            # データをクリーンアップ
            clean_df = df[['Date', 'GSCPI']].dropna()
            clean_df = clean_df.copy()

            def parse_date(value):
                try:
                    if pd.isna(value):
                        return None

                    # すでにdatetime型の場合
                    if isinstance(value, pd.Timestamp):
                        return value

                    # 文字列の場合（DD-MMM-YYYY形式など）
                    if isinstance(value, str):
                        return pd.to_datetime(value, errors='coerce')

                    # その他の場合はpandasに任せる
                    return pd.to_datetime(value, errors='coerce')
                except Exception:
                    return None

            clean_df['Date'] = clean_df['Date'].apply(parse_date)
            clean_df = clean_df.dropna()

            # API用フォーマットに変換
            result = []
            for _, row in clean_df.iterrows():
                date_str = row['Date'].strftime('%Y-%m-%d')
                value = float(row['GSCPI']) if pd.notna(row['GSCPI']) else None

                if value is not None:
                    result.append({
                        "date": date_str,
                        "value": round(value, 3)
                    })

            # 日付順にソート（昇順）
            result.sort(key=lambda x: x["date"])

            if result:
                print(f"GSCPI date range: {result[0]['date']} to {result[-1]['date']}")

            return result

        except Exception as e:
            print(f"Error processing GSCPI data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        """
        次回発表日を計算（毎月第4営業日）

        Returns:
            次回発表日情報
        """
        try:
            today = date.today()

            # 当月の第4営業日を計算
            year = today.year
            month = today.month

            # 今月の第4営業日
            fourth_business_day = self._get_nth_business_day(year, month, 4)

            # 今月の第4営業日が過ぎていたら来月
            if fourth_business_day and today > fourth_business_day:
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                fourth_business_day = self._get_nth_business_day(year, month, 4)

            if fourth_business_day:
                return {
                    "date": fourth_business_day.strftime("%Y-%m-%d"),
                    "time": "10:00 ET"
                }

            return None

        except Exception as e:
            print(f"Error calculating next release date: {e}")
            return None

    def _get_nth_business_day(self, year: int, month: int, n: int) -> Optional[date]:
        """
        指定月のn番目の営業日を取得

        Args:
            year: 年
            month: 月
            n: n番目

        Returns:
            n番目の営業日
        """
        try:
            from calendar import monthrange

            _, last_day = monthrange(year, month)
            business_days = 0

            for day in range(1, last_day + 1):
                d = date(year, month, day)
                # 月-金を営業日とする（祝日は考慮しない簡易版）
                if d.weekday() < 5:  # 0=月, 4=金
                    business_days += 1
                    if business_days == n:
                        return d

            return None

        except Exception:
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        毎月第4営業日以降の10:00 ET以降に3分間隔でチェック

        Args:
            last_updated_str: 最終更新日時（ISO形式）

        Returns:
            更新すべき場合True
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            today = date.today()

            # 今月の第4営業日を取得
            fourth_business_day = self._get_nth_business_day(today.year, today.month, 4)

            if not fourth_business_day:
                return False

            # 第4営業日以降かつ10:00 ET以降かチェック
            if today >= fourth_business_day:
                # 10:00 ET = 約00:00 JST（次の日）または23:00 JST（夏時間）
                release_time_et = datetime(
                    today.year, today.month, today.day,
                    10, 0, 0,
                    tzinfo=ET
                )
                release_time_jst = release_time_et.astimezone(JST)

                # 発表時刻後かつキャッシュが発表前の場合
                if now >= release_time_jst and last_updated < release_time_jst:
                    # データが更新されたかチェック（3分間隔）
                    cached_data = redis_client.get(self.DATA_CACHE_KEY)
                    if cached_data:
                        data = cached_data.get("data", [])
                        if data:
                            latest_date = data[-1].get("date", "")
                            # 最新データの日付が先月以前なら更新
                            if latest_date:
                                latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
                                if latest_dt.month < today.month or latest_dt.year < today.year:
                                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh condition: {e}")
            return False

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not GSCPI_CACHE_FILE.exists():
                return None
            with open(GSCPI_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(GSCPI_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "GSCPI",
            "source": "NY Fed Excel",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": cached_data.get("next_release") if cached_data else None,
            "file_cache_exists": GSCPI_CACHE_FILE.exists()
        }


# シングルトンインスタンス
gscpi_service = GSCPIService()
