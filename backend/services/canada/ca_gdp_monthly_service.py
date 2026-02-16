"""
カナダ月次GDPサービス

指標:
- 月次GDP（前月比: MoM）
- 月次GDP（前年比: YoY）
- 速報値（Advance Estimate）

データソース:
- Statistics Canada Table 36-10-0434-01
- 月次GDP（産業別、季節調整済み年率）
- プレスリリース（速報値）

発表スケジュール:
- 月次（対象月の約2ヶ月後）
- 発表時刻: 08:30 ET
"""
import json
import zipfile
import io
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd
from bs4 import BeautifulSoup

from core.redis_client import redis_client
from services.canada.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
TORONTO = ZoneInfo("America/Toronto")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "canada" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ca_gdp_monthly_cache.json"

# Statistics Canada CSV URL
# Table 36-10-0434-01: 月次GDP（産業別）
STATCAN_GDP_MONTHLY_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/36100434-eng.zip"

# Statistics Canada プレスリリースURL（速報値取得用）
# パターン: https://www150.statcan.gc.ca/n1/daily-quotidien/YYMMDD/dqYYMMDDa-eng.htm
STATCAN_DAILY_QUOTIDIEN_BASE = "https://www150.statcan.gc.ca/n1/daily-quotidien"

# FMPイベントパターン
FMP_GDP_MONTHLY_PATTERN = "Gross Domestic Product MoM"
CA_GDP_MONTHLY_ECONALPHA_ID = "ca_gdp_monthly"

# 月名マッピング（英語 -> 月番号）
MONTH_NAME_TO_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
}


class CaGdpMonthlyService:
    """カナダ月次GDPサービス"""

    DATA_CACHE_KEY = "canada:ca_gdp_monthly:data"
    ADVANCE_CACHE_KEY = "canada:ca_gdp_monthly:advance"
    CACHE_TTL = 86400  # 24時間
    ADVANCE_CACHE_TTL = 3600  # 1時間（速報値は頻繁に確認）

    def __init__(self):
        pass

    def get_ca_gdp_monthly_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """カナダ月次GDPデータを取得（速報値含む）"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    # キャッシュから速報値も取得
                    advance_estimate = self._get_advance_estimate_cached()
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "advance_estimate": advance_estimate,
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            # 最新値を取得
            latest = result[-1] if result else None
            next_release = get_next_release_by_pattern(FMP_GDP_MONTHLY_PATTERN, country="CA")

            # 速報値を取得
            advance_estimate = self._fetch_advance_estimate()

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Statistics Canada",
                    "table": "36-10-0434-01",
                    "indicator": "Monthly GDP",
                    "description": "カナダ月次GDP（産業別）",
                    "unit": "%",
                    "frequency": "monthly",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=self.CACHE_TTL)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "advance_estimate": advance_estimate,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            advance_estimate = self._get_advance_estimate_cached()
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "advance_estimate": advance_estimate,
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "advance_estimate": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """Statistics Canadaから月次GDPデータを取得"""
        try:
            print(f"[CaGdpMonthly] Fetching data from: {STATCAN_GDP_MONTHLY_URL}")

            resp = requests.get(STATCAN_GDP_MONTHLY_URL, timeout=90)
            resp.raise_for_status()

            z = zipfile.ZipFile(io.BytesIO(resp.content))
            csv_name = [n for n in z.namelist() if n.endswith('.csv') and not n.startswith('_')][0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

            print(f"[CaGdpMonthly] Columns: {df.columns.tolist()}")

            # 全産業、季節調整済み年率、Chained (2017) dollarsのデータをフィルタ
            gdp_data = df[
                (df['North American Industry Classification System (NAICS)'] == 'All industries [T001]') &
                (df['Seasonal adjustment'] == 'Seasonally adjusted at annual rates') &
                (df['Prices'] == 'Chained (2017) dollars')
            ].copy()

            print(f"[CaGdpMonthly] Found {len(gdp_data)} monthly GDP records")

            # 日付と値を辞書に格納
            gdp_values = {}
            for _, row in gdp_data.iterrows():
                date_str = row['REF_DATE']  # 形式: "2024-01" (YYYY-MM)
                value = row['VALUE']

                if pd.isna(value):
                    continue

                try:
                    # 月形式を日付に変換 (例: "2024-01" -> "2024-01-01")
                    formatted_date = self._month_to_date(date_str)
                    if formatted_date:
                        gdp_values[formatted_date] = float(value)
                except (ValueError, TypeError):
                    continue

            print(f"[CaGdpMonthly] Parsed {len(gdp_values)} GDP values")

            # MoMとYoYを計算
            result = self._calculate_growth_rates(gdp_values)

            print(f"[CaGdpMonthly] Loaded {len(result)} monthly records")
            if result:
                print(f"[CaGdpMonthly] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CaGdpMonthly] Latest: {latest['date']} MoM={latest.get('mom')}% YoY={latest.get('yoy')}%")

            return result

        except Exception as e:
            print(f"[CaGdpMonthly] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _month_to_date(self, month_str: str) -> Optional[str]:
        """月形式を日付に変換（例: "2024-01" -> "2024-01-01"）"""
        try:
            month_str = month_str.strip()
            # 形式: "2024-01" -> "2024-01-01"
            if len(month_str) == 7 and '-' in month_str:
                return f"{month_str}-01"
            return None
        except Exception:
            return None

    def _calculate_growth_rates(self, gdp_values: Dict[str, float]) -> List[Dict[str, Any]]:
        """MoM（前月比）とYoY（前年比）を計算

        Args:
            gdp_values: 日付 -> GDP絶対値（Chained 2017 dollars）
        """
        # 日付でソート
        sorted_dates = sorted(gdp_values.keys())
        result = []

        for i, date_str in enumerate(sorted_dates):
            current_value = gdp_values[date_str]
            item = {
                "date": date_str,
                "value": round(current_value, 2),
            }

            # MoM（前月比）を計算
            if i > 0:
                prev_date = sorted_dates[i - 1]
                prev_value = gdp_values[prev_date]
                if prev_value > 0:
                    mom = ((current_value - prev_value) / prev_value) * 100
                    item["mom"] = round(mom, 2)

            # YoY（前年比）を計算
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            prev_year_date = f"{dt.year - 1}-{dt.month:02d}-01"
            if prev_year_date in gdp_values:
                prev_year_value = gdp_values[prev_year_date]
                if prev_year_value > 0:
                    yoy = ((current_value - prev_year_value) / prev_year_value) * 100
                    item["yoy"] = round(yoy, 2)

            # MoMまたはYoYがある場合のみ追加
            if "mom" in item or "yoy" in item:
                result.append(item)

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_GDP_MONTHLY_PATTERN, last_updated_str, country="CA")
        except Exception:
            # FMP判定失敗時は24時間経過でリフレッシュ
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                age = now - last_updated
                return age.total_seconds() > 86400
            except Exception:
                return True

    def _get_advance_estimate_cached(self) -> Optional[Dict[str, Any]]:
        """キャッシュから速報値を取得（なければフェッチ）"""
        cached = redis_client.get(self.ADVANCE_CACHE_KEY)
        if cached:
            return cached
        return self._fetch_advance_estimate()

    def _fetch_advance_estimate(self) -> Optional[Dict[str, Any]]:
        """
        速報値（Advance Estimate）を取得

        取得方法:
        - Statistics Canadaプレスリリースから次月の速報値を取得
        - "Advance information indicates that real GDP increased/decreased X.X% in MONTH"

        注意:
        - FMPのactual値は確定値であり、速報値ではない
        - 速報値はプレスリリースのみから取得する
        - 確定値はStatistics CanadaのCSVから取得する

        Returns:
            速報値情報（プレスリリースから取得）、なければNone
        """
        # プレスリリースから速報値のみを取得
        return self._fetch_advance_from_press_release()

    def _fetch_latest_from_fmp(self) -> Optional[Dict[str, Any]]:
        """
        FMP DBから最新の確定値を取得

        NOTE: このメソッドは現在使用されていません。
        速報値はプレスリリースから取得し、確定値はStatistics Canada CSVから取得します。
        FMPのactual値は確定値であり、速報値ではありません。

        将来的にFMPの確定値がCSVより新しい場合の比較用途で使用する可能性があります。
        """
        try:
            import os
            from dotenv import load_dotenv
            load_dotenv()

            from sqlalchemy import create_engine, text
            from sqlalchemy.orm import sessionmaker

            DATABASE_URL = os.getenv('DATABASE_URL')
            if not DATABASE_URL:
                print("[CaGdpMonthly] DATABASE_URL not configured")
                return None

            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)

            with Session() as session:
                # 最新の月次GDP MoMイベントを取得
                # actual=NULLでestimateがあるもの = まだ発表前の速報値
                query = text("""
                    SELECT event, datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'CA'
                      AND event LIKE 'Gross Domestic Product MoM%'
                      AND datetime_utc <= NOW()
                    ORDER BY datetime_utc DESC
                    LIMIT 5
                """)
                rows = session.execute(query).fetchall()

                if not rows:
                    return None

                # 最新の発表済みイベント（actual != NULL）を探す
                for row in rows:
                    event_name = row[0]
                    dt_utc = row[1]
                    actual = row[2]
                    estimate = row[3]
                    previous = row[4]

                    if actual is not None:
                        # イベント名から対象月を抽出（例: "Gross Domestic Product MoM (Dec)"）
                        month_match = re.search(r'\((\w+)\)', event_name)
                        if not month_match:
                            continue

                        month_abbr = month_match.group(1).lower()
                        month_abbr_to_num = {
                            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                            "may": 5, "jun": 6, "jul": 7, "aug": 8,
                            "sep": 9, "oct": 10, "nov": 11, "dec": 12
                        }
                        month_num = month_abbr_to_num.get(month_abbr)
                        if not month_num:
                            continue

                        # 年を推定（発表日時から判断）
                        release_year = dt_utc.year
                        # 発表月が1-2月で対象月が11-12月の場合は前年
                        if dt_utc.month <= 2 and month_num >= 11:
                            target_year = release_year - 1
                        else:
                            target_year = release_year

                        target_date = f"{target_year}-{month_num:02d}-01"

                        advance_data = {
                            "date": target_date,
                            "mom": round(float(actual), 2),
                            "estimate": round(float(estimate), 2) if estimate else None,
                            "previous": round(float(previous), 2) if previous else None,
                            "is_advance": False,  # actualがあるので確定値
                            "source": "fmp",
                            "event": event_name,
                            "release_date": dt_utc.isoformat(),
                            "fetched_at": datetime.now(JST).isoformat(),
                        }

                        # キャッシュに保存
                        redis_client.set(self.ADVANCE_CACHE_KEY, advance_data, expire=self.ADVANCE_CACHE_TTL)

                        print(f"[CaGdpMonthly] FMP data: {target_date} MoM={actual}% (estimate={estimate}%)")
                        return advance_data

                # 発表前のイベント（actual=NULL、estimate!=NULL）を速報値として返す
                for row in rows:
                    event_name = row[0]
                    dt_utc = row[1]
                    actual = row[2]
                    estimate = row[3]
                    previous = row[4]

                    if actual is None and estimate is not None:
                        month_match = re.search(r'\((\w+)\)', event_name)
                        if not month_match:
                            continue

                        month_abbr = month_match.group(1).lower()
                        month_abbr_to_num = {
                            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                            "may": 5, "jun": 6, "jul": 7, "aug": 8,
                            "sep": 9, "oct": 10, "nov": 11, "dec": 12
                        }
                        month_num = month_abbr_to_num.get(month_abbr)
                        if not month_num:
                            continue

                        release_year = dt_utc.year
                        if dt_utc.month <= 2 and month_num >= 11:
                            target_year = release_year - 1
                        else:
                            target_year = release_year

                        target_date = f"{target_year}-{month_num:02d}-01"

                        advance_data = {
                            "date": target_date,
                            "mom": round(float(estimate), 2),  # 予測値を速報値として使用
                            "estimate": round(float(estimate), 2),
                            "previous": round(float(previous), 2) if previous else None,
                            "is_advance": True,  # まだ発表前なので速報値
                            "source": "fmp_estimate",
                            "event": event_name,
                            "scheduled_release": dt_utc.isoformat(),
                            "fetched_at": datetime.now(JST).isoformat(),
                        }

                        redis_client.set(self.ADVANCE_CACHE_KEY, advance_data, expire=self.ADVANCE_CACHE_TTL)

                        print(f"[CaGdpMonthly] FMP estimate: {target_date} MoM={estimate}% (advance)")
                        return advance_data

                return None

        except Exception as e:
            print(f"[CaGdpMonthly] Error fetching from FMP DB: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_advance_from_press_release(self) -> Optional[Dict[str, Any]]:
        """
        Statistics Canadaプレスリリースから速報値（Advance Estimate）を取得

        プレスリリースのURLパターン:
        https://www150.statcan.gc.ca/n1/daily-quotidien/YYMMDD/dqYYMMDDa-eng.htm

        速報値の記載パターン:
        "Advance information indicates that real GDP increased/decreased X.X% in MONTH"
        """
        try:
            # 最新のプレスリリースURLを特定
            release_url = self._find_latest_gdp_release_url()
            if not release_url:
                print("[CaGdpMonthly] Could not find latest GDP release URL")
                return None

            print(f"[CaGdpMonthly] Fetching advance estimate from: {release_url}")

            resp = requests.get(release_url, timeout=30)
            if resp.status_code != 200:
                print(f"[CaGdpMonthly] Failed to fetch release page: HTTP {resp.status_code}")
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text().replace('\xa0', ' ')

            # 速報値のパターンを抽出
            pattern = r'Advance information indicates that real GDP (increased|decreased) (\d+\.\d+)% in (\w+)'
            match = re.search(pattern, text, re.IGNORECASE)

            if not match:
                print("[CaGdpMonthly] No advance estimate pattern found in release")
                return None

            direction = match.group(1).lower()
            value = float(match.group(2))
            month_name = match.group(3).lower()

            if direction == 'decreased':
                value = -value

            month_num = MONTH_NAME_TO_NUM.get(month_name)
            if not month_num:
                print(f"[CaGdpMonthly] Unknown month name: {month_name}")
                return None

            today = date.today()
            if month_num > today.month:
                target_year = today.year - 1
            else:
                target_year = today.year

            target_date = f"{target_year}-{month_num:02d}-01"

            advance_data = {
                "date": target_date,
                "mom": round(value, 2),
                "is_advance": True,
                "source": "press_release",
                "source_url": release_url,
                "fetched_at": datetime.now(JST).isoformat(),
            }

            redis_client.set(self.ADVANCE_CACHE_KEY, advance_data, expire=self.ADVANCE_CACHE_TTL)

            print(f"[CaGdpMonthly] Press release advance: {target_date} MoM={value}%")
            return advance_data

        except Exception as e:
            print(f"[CaGdpMonthly] Error fetching from press release: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _find_latest_gdp_release_url(self) -> Optional[str]:
        """
        最新のGDPプレスリリースURLを特定
        """
        try:
            today = date.today()

            for days_ago in range(30):
                check_date = today - timedelta(days=days_ago)
                date_str = check_date.strftime("%y%m%d")
                url = f"{STATCAN_DAILY_QUOTIDIEN_BASE}/{date_str}/dq{date_str}a-eng.htm"

                try:
                    resp = requests.head(url, timeout=10, allow_redirects=True)
                    if resp.status_code == 200:
                        full_resp = requests.get(url, timeout=15)
                        if 'Gross domestic product by industry' in full_resp.text:
                            return url
                except requests.RequestException:
                    continue

            return None

        except Exception as e:
            print(f"[CaGdpMonthly] Error finding latest release URL: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CaGdpMonthly] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CaGdpMonthly] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        advance_exists = redis_client.exists(self.ADVANCE_CACHE_KEY)
        advance_data = redis_client.get(self.ADVANCE_CACHE_KEY) if advance_exists else None

        return {
            "indicator": "Canada Monthly GDP",
            "source": "Statistics Canada",
            "table": "36-10-0434-01",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "advance_estimate": advance_data,
            "advance_cache_exists": advance_exists,
            "next_release": get_next_release_by_pattern(FMP_GDP_MONTHLY_PATTERN, country="CA"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ca_gdp_monthly_service = CaGdpMonthlyService()
