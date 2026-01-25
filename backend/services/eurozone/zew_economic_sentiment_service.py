"""
ZEW景況感指数サービス
ZEW研究所のExcelファイルからZEW Economic Sentiment Indexデータを取得

指標:
- ZEW Indicator of Economic Sentiment Germany (景況感指数): 経済見通しに関する期待
- Economic Situation Germany (現況指数): 現在の経済状況の評価

データソース:
- ZEW (ドイツ経済研究センター): https://ftp.zew.de/pub/zew-docs/div/konjunktur.xls
- FMP economic_calendar_events（速報値補完用）

発表スケジュール:
- 月次（毎月第2または第3火曜日 11:00 CET）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import io
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "zew_economic_sentiment_cache.json"


class ZEWEconomicSentimentService:
    """ZEW景況感指数サービス (ZEW Excel + FMP)"""

    DATA_CACHE_KEY = "economy:zew_economic_sentiment:data"
    ECONALPHA_ID = "zew_economic_sentiment_index"

    # ZEWデータソースURL
    ZEW_URL = "https://zew.de/fileadmin/FTP/div/konjunktur.xls"
    # フォールバックURL
    ZEW_URL_FALLBACK = "https://ftp.zew.de/pub/zew-docs/div/konjunktur.xls"

    def __init__(self):
        pass

    def get_zew_economic_sentiment_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        ZEW景況感指数データを取得

        Returns:
            {
                "sentiment": [...],  # 景況感指数データ（期待）
                "situation": [...],  # 現況指数データ
                "latest_sentiment": {...},
                "latest_situation": {...},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "sentiment": cached_data.get("sentiment", []),
                        "situation": cached_data.get("situation", []),
                        "latest_sentiment": cached_data.get("latest_sentiment"),
                        "latest_situation": cached_data.get("latest_situation"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 1. ZEW Excelからデータを取得
        zew_data = self._load_from_zew()

        # 2. FMP DBから速報データを取得
        fmp_data = self._load_from_fmp_db()

        # 3. データをマージ（ZEW < FMP の順で上書き）
        merged_data = self._merge_sources(zew_data, fmp_data)

        sentiment_data = merged_data.get("sentiment", [])
        situation_data = merged_data.get("situation", [])

        if sentiment_data or situation_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            latest_sentiment = sentiment_data[-1] if sentiment_data else None
            latest_situation = situation_data[-1] if situation_data else None

            cache_payload = {
                "sentiment": sentiment_data,
                "situation": situation_data,
                "latest_sentiment": latest_sentiment,
                "latest_situation": latest_situation,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "sentiment": sentiment_data,
                "situation": situation_data,
                "latest_sentiment": latest_sentiment,
                "latest_situation": latest_situation,
                "next_release": next_release,
                "cached": False,
                "source": "zew + fmp",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
            return {
                "sentiment": file_cache.get("sentiment", []),
                "situation": file_cache.get("situation", []),
                "latest_sentiment": file_cache.get("latest_sentiment"),
                "latest_situation": file_cache.get("latest_situation"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "sentiment": [],
            "situation": [],
            "latest_sentiment": None,
            "latest_situation": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    # =========================================================================
    # ZEW Excel関連メソッド
    # =========================================================================

    def _load_from_zew(self) -> Dict[str, List[Dict[str, Any]]]:
        """ZEW Excelファイルからデータを取得"""
        print("[ZEWEconomicSentiment] Fetching data from ZEW Excel...")

        # まずメインURLを試す
        excel_content = self._fetch_excel(self.ZEW_URL)
        if not excel_content:
            # フォールバックURLを試す
            print("[ZEWEconomicSentiment] Main URL failed, trying fallback...")
            excel_content = self._fetch_excel(self.ZEW_URL_FALLBACK)

        if not excel_content:
            print("[ZEWEconomicSentiment] Failed to fetch Excel from ZEW")
            return {"sentiment": [], "situation": []}

        return self._parse_zew_excel(excel_content)

    def _fetch_excel(self, url: str) -> Optional[bytes]:
        """ExcelファイルをURLから取得"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                return response.content
            print(f"[ZEWEconomicSentiment] HTTP {response.status_code} from {url}")
            return None
        except Exception as e:
            print(f"[ZEWEconomicSentiment] Error fetching Excel: {e}")
            return None

    def _parse_zew_excel(self, excel_content: bytes) -> Dict[str, List[Dict[str, Any]]]:
        """
        ZEW Excelファイルをパース

        Excel構造:
        - Sheet: "data" または "longterm"
        - 列: 日付, ZEW Indicator of Economic Sentiment Germany, Economic Situation Germany
        """
        try:
            # xlrdでExcelを読み込む（.xls形式）
            df = pd.read_excel(
                io.BytesIO(excel_content),
                sheet_name=0,  # 最初のシート
                engine='xlrd'
            )

            # デバッグ: 列名を確認
            print(f"[ZEWEconomicSentiment] Columns: {df.columns.tolist()}")

            # 列名を検索（部分一致）
            sentiment_col = None
            situation_col = None
            date_col = None

            for col in df.columns:
                col_str = str(col).lower()
                if 'indicator of economic sentiment' in col_str or 'zew indicator' in col_str:
                    sentiment_col = col
                elif 'economic situation' in col_str or 'situation' in col_str:
                    if 'indicator' not in col_str:  # sentimentと区別
                        situation_col = col
                elif 'date' in col_str or 'month' in col_str or 'zeit' in col_str:
                    date_col = col

            # 日付列が見つからない場合、最初の列を使用
            if date_col is None:
                date_col = df.columns[0]

            print(f"[ZEWEconomicSentiment] Date column: {date_col}")
            print(f"[ZEWEconomicSentiment] Sentiment column: {sentiment_col}")
            print(f"[ZEWEconomicSentiment] Situation column: {situation_col}")

            sentiment_data = []
            situation_data = []

            for _, row in df.iterrows():
                try:
                    # 日付を取得
                    date_value = row[date_col]
                    if pd.isna(date_value):
                        continue

                    # 日付を正規化
                    date_str = self._normalize_date(date_value)
                    if not date_str:
                        continue

                    # 景況感指数（期待）
                    if sentiment_col and pd.notna(row.get(sentiment_col)):
                        try:
                            value = float(row[sentiment_col])
                            sentiment_data.append({
                                'date': date_str,
                                'value': round(value, 1),
                                'source': 'zew',
                            })
                        except (ValueError, TypeError):
                            pass

                    # 現況指数
                    if situation_col and pd.notna(row.get(situation_col)):
                        try:
                            value = float(row[situation_col])
                            situation_data.append({
                                'date': date_str,
                                'value': round(value, 1),
                                'source': 'zew',
                            })
                        except (ValueError, TypeError):
                            pass

                except Exception as e:
                    continue

            # 日付でソート
            sentiment_data.sort(key=lambda x: x['date'])
            situation_data.sort(key=lambda x: x['date'])

            print(f"[ZEWEconomicSentiment] Loaded {len(sentiment_data)} sentiment, {len(situation_data)} situation records from ZEW")
            return {"sentiment": sentiment_data, "situation": situation_data}

        except Exception as e:
            print(f"[ZEWEconomicSentiment] Error parsing Excel: {e}")
            import traceback
            traceback.print_exc()
            return {"sentiment": [], "situation": []}

    def _normalize_date(self, date_value) -> Optional[str]:
        """日付値を 'YYYY-MM' 形式に正規化"""
        try:
            if isinstance(date_value, datetime):
                return date_value.strftime("%Y-%m")
            elif isinstance(date_value, pd.Timestamp):
                return date_value.strftime("%Y-%m")
            elif isinstance(date_value, str):
                # 様々な形式を試す
                for fmt in ['%Y-%m', '%Y/%m', '%m/%Y', '%Y-%m-%d', '%Y/%m/%d']:
                    try:
                        dt = datetime.strptime(date_value.strip(), fmt)
                        return dt.strftime("%Y-%m")
                    except ValueError:
                        continue
                # 月名形式を試す（例: "January 2024"）
                try:
                    dt = pd.to_datetime(date_value)
                    return dt.strftime("%Y-%m")
                except:
                    pass
            elif isinstance(date_value, (int, float)):
                # Excel serial date
                try:
                    dt = pd.to_datetime(date_value, origin='1899-12-30', unit='D')
                    return dt.strftime("%Y-%m")
                except:
                    pass
            return None
        except Exception:
            return None

    # =========================================================================
    # FMP DB関連メソッド
    # =========================================================================

    def _load_from_fmp_db(self) -> Dict[str, List[Dict[str, Any]]]:
        """FMP economic_calendar_eventsから速報データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                # ZEW Economic Sentiment Index
                sentiment_query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'DE'
                      AND event ILIKE '%ZEW Economic Sentiment Index%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                sentiment_rows = session.execute(sentiment_query).fetchall()

                # ZEW Current Conditions（現況指数）
                situation_query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'DE'
                      AND event ILIKE '%ZEW Current Conditions%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                situation_rows = session.execute(situation_query).fetchall()

                sentiment_result = []
                situation_result = []
                seen_sentiment_dates = set()
                seen_situation_dates = set()

                for row in sentiment_rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m")
                        if date_str in seen_sentiment_dates:
                            continue
                        seen_sentiment_dates.add(date_str)

                        sentiment_result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                            "source": "fmp",
                        })

                for row in situation_rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        date_str = dt_utc.strftime("%Y-%m")
                        if date_str in seen_situation_dates:
                            continue
                        seen_situation_dates.add(date_str)

                        situation_result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                            "source": "fmp",
                        })

                print(f"[ZEWEconomicSentiment] Loaded {len(sentiment_result)} sentiment, {len(situation_result)} situation records from FMP DB")
                return {"sentiment": sentiment_result, "situation": situation_result}

        except Exception as e:
            print(f"[ZEWEconomicSentiment] Error loading from FMP DB: {e}")
            return {"sentiment": [], "situation": []}

    # =========================================================================
    # データマージ
    # =========================================================================

    def _merge_sources(
        self,
        zew_data: Dict[str, List[Dict[str, Any]]],
        fmp_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        ZEWとFMPのデータをマージ
        優先順位: zew_data < fmp_data（FMPの速報が最新）
        """
        # Sentiment データのマージ
        sentiment_merged: Dict[str, Dict[str, Any]] = {}

        for d in zew_data.get("sentiment", []):
            sentiment_merged[d["date"]] = d.copy()

        # FMP速報で上書き
        for d in fmp_data.get("sentiment", []):
            date = d["date"]
            if date in sentiment_merged:
                if sentiment_merged[date].get("source") != "zew":
                    sentiment_merged[date] = d.copy()
            else:
                sentiment_merged[date] = d.copy()

        # Situation データのマージ
        situation_merged: Dict[str, Dict[str, Any]] = {}

        for d in zew_data.get("situation", []):
            situation_merged[d["date"]] = d.copy()

        for d in fmp_data.get("situation", []):
            date = d["date"]
            if date in situation_merged:
                if situation_merged[date].get("source") != "zew":
                    situation_merged[date] = d.copy()
            else:
                situation_merged[date] = d.copy()

        sentiment_result = sorted(sentiment_merged.values(), key=lambda x: x["date"])
        situation_result = sorted(situation_merged.values(), key=lambda x: x["date"])

        return {"sentiment": sentiment_result, "situation": situation_result}

    # =========================================================================
    # キャッシュ関連メソッド
    # =========================================================================

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ZEWEconomicSentiment] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ZEWEconomicSentiment] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ZEW Economic Sentiment Index",
            "source": "ZEW (Excel) + FMP",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "sentiment_count": len(cached_data.get("sentiment", [])) if cached_data else 0,
            "situation_count": len(cached_data.get("situation", [])) if cached_data else 0,
            "latest_sentiment": cached_data.get("latest_sentiment") if cached_data else None,
            "latest_situation": cached_data.get("latest_situation") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
zew_economic_sentiment_service = ZEWEconomicSentimentService()
