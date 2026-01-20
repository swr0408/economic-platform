"""
UK ONS労働生産性サービス
ONS Time Series APIから労働生産性データを取得

指標:
- LZVB: Output per hour worked (Index 2022=100) - 時間当たり生産性
- A4YM: Output per worker (Index 2022=100) - 労働者当たり生産性
- DMWO: Unit labour costs (QoQ % change) - 単位労働コスト

データソース:
- ONS Time Series Data（確定値）
- ONS Flash Estimate（速報値）- 最新四半期のみ
- https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/labourproductivity

発表スケジュール:
- FMPカレンダーから自動取得（Labour Productivity QoQパターン）
- 四半期発表

キャッシュ方式: FMP発表日時ベース判定方式

速報値（Flash Estimate）について:
- Time Seriesより1四半期先のデータを提供
- /articles/ukproductivityintroduction/latest から最新記事を取得
- 速報値にはis_flash=Trueフラグを付与
"""
import csv
import json
import requests
from datetime import datetime
from io import StringIO
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path
import re

from core.redis_client import redis_client
from services.uk.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ons_productivity_cache.json"


class ONSProductivityService:
    """UK ONS労働生産性サービス"""

    DATA_CACHE_KEY = "uk:ons_productivity:data"
    ECONALPHA_ID = "ons_productivity"

    # ONS Time Series API URLs
    # LZVB: Output per hour worked (Index 2022=100)
    LZVB_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peopleinwork/labourproductivity/timeseries/lzvb/prdy"
    # A4YM: Output per worker (Index 2022=100)
    A4YM_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peopleinwork/labourproductivity/timeseries/a4ym/prdy"
    # DMWO: Unit labour costs (QoQ % change)
    DMWO_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peopleinwork/labourproductivity/timeseries/dmwo/ucst"

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERN = "Labour Productivity QoQ"

    # Flash Estimate URL
    FLASH_ESTIMATE_LATEST_URL = "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/labourproductivity/articles/ukproductivityintroduction/latest"
    ONS_BASE_URL = "https://www.ons.gov.uk"

    def __init__(self):
        pass

    def get_ons_productivity_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ONS労働生産性データを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "lzvb": cached_data.get("lzvb", {}),
                        "a4ym": cached_data.get("a4ym", {}),
                        "dmwo": cached_data.get("dmwo", {}),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ONSからデータを取得
        api_result = self._fetch_all_from_ons()

        if api_result:
            # 最新値を決定（LZVBのYoYデータから取得）
            lzvb_yoy = api_result.get("lzvb", {}).get("yoy", [])
            latest = lzvb_yoy[-1] if lzvb_yoy else None

            cache_payload = {
                "lzvb": api_result.get("lzvb", {}),
                "a4ym": api_result.get("a4ym", {}),
                "dmwo": api_result.get("dmwo", {}),
                "latest": latest,
                "metadata": api_result.get("metadata", {}),
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "lzvb": api_result.get("lzvb", {}),
                "a4ym": api_result.get("a4ym", {}),
                "dmwo": api_result.get("dmwo", {}),
                "latest": latest,
                "metadata": api_result.get("metadata", {}),
                "next_release": next_release,
                "cached": False,
                "source": "ons_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "lzvb": file_cache.get("lzvb", {}),
                "a4ym": file_cache.get("a4ym", {}),
                "dmwo": file_cache.get("dmwo", {}),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "lzvb": {},
            "a4ym": {},
            "dmwo": {},
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得 - FMPカレンダーから検索"""
        try:
            return get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country="GB")
        except Exception as e:
            print(f"[ONS Productivity] Error getting next release: {e}")
            return None

    def _fetch_csv_data(self, url: str, series_name: str) -> Optional[Dict[str, Any]]:
        """単一のCSVデータソースをパース"""
        try:
            print(f"[ONS Productivity] Fetching {series_name} from {url}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            csv_reader = csv.reader(StringIO(response.text))

            # ヘッダー行を読み込む
            title_row = next(csv_reader)
            cdid_row = next(csv_reader)
            source_row = next(csv_reader)
            preunit_row = next(csv_reader)
            unit_row = next(csv_reader)
            release_date_row = next(csv_reader)
            next_release_row = next(csv_reader)
            notes_row = next(csv_reader)

            title = title_row[1] if len(title_row) > 1 else series_name
            cdid = cdid_row[1] if len(cdid_row) > 1 else ""
            unit = unit_row[1] if len(unit_row) > 1 else ""
            release_date = release_date_row[1] if len(release_date_row) > 1 else ""
            next_release_ons = next_release_row[1] if len(next_release_row) > 1 else ""

            # 四半期データを読み込む（形式: "YYYY QN"）
            data_points = []

            for row in csv_reader:
                if len(row) >= 2 and row[0] and row[1]:
                    try:
                        period_str = row[0].strip()
                        value = float(row[1].strip())

                        # 四半期データのみ処理（形式: "YYYY QN"）
                        if " Q" in period_str:
                            # "YYYY QN" 形式をパース（例: "2024 Q1"）
                            year_str, quarter_str = period_str.split(" Q")
                            year = int(year_str)
                            quarter = int(quarter_str)

                            # 四半期の最初の月に変換
                            month = (quarter - 1) * 3 + 1
                            date_str = f"{year}-{month:02d}-01"

                            data_points.append({
                                "date": date_str,
                                "value": round(value, 2),
                                "period": period_str,
                            })
                    except (ValueError, IndexError):
                        continue

            print(f"[ONS Productivity] Extracted {len(data_points)} data points for {series_name}")

            return {
                "data": data_points,
                "metadata": {
                    "title": title,
                    "cdid": cdid,
                    "unit": unit,
                    "release_date": release_date,
                    "next_release_ons": next_release_ons,
                },
            }

        except Exception as e:
            print(f"[ONS Productivity] Error fetching {series_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_yoy_change(self, data_points: List[Dict]) -> List[Dict]:
        """前年比（YoY）を計算"""
        yoy_data = []

        # 日付でソート
        sorted_data = sorted(data_points, key=lambda x: x["date"])

        for i, point in enumerate(sorted_data):
            # 4四半期前（1年前）のポイントを探す
            if i >= 4:
                prev_point = sorted_data[i - 4]
                current_value = point["value"]
                prev_value = prev_point["value"]

                if prev_value and prev_value != 0:
                    yoy_change = ((current_value - prev_value) / prev_value) * 100
                    yoy_data.append({
                        "date": point["date"],
                        "period": point["period"],
                        "value": current_value,
                        "yoy": round(yoy_change, 2),
                    })

        return yoy_data

    def _calculate_qoq_change(self, data_points: List[Dict]) -> List[Dict]:
        """前期比（QoQ）を計算"""
        qoq_data = []

        # 日付でソート
        sorted_data = sorted(data_points, key=lambda x: x["date"])

        for i in range(1, len(sorted_data)):
            current_point = sorted_data[i]
            prev_point = sorted_data[i - 1]

            current_value = current_point["value"]
            prev_value = prev_point["value"]

            if prev_value and prev_value != 0:
                qoq_change = ((current_value - prev_value) / prev_value) * 100
                qoq_data.append({
                    "date": current_point["date"],
                    "period": current_point["period"],
                    "value": current_value,
                    "qoq": round(qoq_change, 2),
                })

        return qoq_data

    def _fetch_all_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONSから全生産性データを取得"""
        try:
            # 各系列を取得
            lzvb_data = self._fetch_csv_data(self.LZVB_CSV_URL, "Output per hour (LZVB)")
            a4ym_data = self._fetch_csv_data(self.A4YM_CSV_URL, "Output per worker (A4YM)")
            dmwo_data = self._fetch_csv_data(self.DMWO_CSV_URL, "Unit labour costs (DMWO)")

            if not lzvb_data or not a4ym_data or not dmwo_data:
                print("[ONS Productivity] Failed to fetch one or more productivity series")
                return None

            # LZVBとA4YMのYoY/QoQを計算
            lzvb_yoy = self._calculate_yoy_change(lzvb_data["data"])
            a4ym_yoy = self._calculate_yoy_change(a4ym_data["data"])
            lzvb_qoq = self._calculate_qoq_change(lzvb_data["data"])
            a4ym_qoq = self._calculate_qoq_change(a4ym_data["data"])

            time_series_result = {
                "lzvb": {
                    "data": lzvb_data["data"],
                    "yoy": lzvb_yoy,
                    "qoq": lzvb_qoq,
                    "metadata": lzvb_data["metadata"],
                },
                "a4ym": {
                    "data": a4ym_data["data"],
                    "yoy": a4ym_yoy,
                    "qoq": a4ym_qoq,
                    "metadata": a4ym_data["metadata"],
                },
                "dmwo": {
                    "data": dmwo_data["data"],
                    "metadata": dmwo_data["metadata"],
                },
                "metadata": {
                    "source": "Office for National Statistics",
                    "description": "イギリス労働生産性",
                    "series": {
                        "lzvb": "時間当たり生産性 (Index 2022=100)",
                        "a4ym": "労働者当たり生産性 (Index 2022=100)",
                        "dmwo": "単位労働コスト (QoQ %)",
                    },
                },
            }

            # Flash Estimate（速報値）を取得してマージ
            flash_data = self._fetch_flash_estimate()
            if flash_data:
                time_series_result = self._merge_flash_estimate(time_series_result, flash_data)
                time_series_result["metadata"]["has_flash_estimate"] = True
                print("[ONS Productivity] Flash estimate data merged successfully")
            else:
                time_series_result["metadata"]["has_flash_estimate"] = False
                print("[ONS Productivity] No flash estimate data available")

            return time_series_result

        except Exception as e:
            print(f"[ONS Productivity] Error fetching from ONS: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_flash_estimate(self) -> Optional[Dict[str, Any]]:
        """
        Flash Estimate（速報値）を取得

        Returns:
            {
                "lzvb": [{"date": "2025-07-01", "yoy": 1.1, "qoq": 0.7, "is_flash": True, "period": "2025 Q3"}],
                "a4ym": [{"date": "2025-07-01", "yoy": 0.0, "qoq": 0.2, "is_flash": True, "period": "2025 Q3"}],
            }
        """
        try:
            print("[ONS Productivity] Fetching flash estimate data...")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            # /latest ページからリダイレクト先の実際のURLを取得
            response = requests.get(
                self.FLASH_ESTIMATE_LATEST_URL,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )
            response.raise_for_status()

            # 実際のURL（リダイレクト後）を取得
            actual_url = response.url
            print(f"[ONS Productivity] Flash estimate article URL: {actual_url}")

            # ページ内容からテーブルダウンロードリンクを探す
            html_content = response.text

            # テーブルのダウンロードリンクを探す（形式: /download/table?format=csv&uri=...）
            table_pattern = r'/download/table\?format=csv&uri=([^"\']+)'
            matches = re.findall(table_pattern, html_content)

            if not matches:
                print("[ONS Productivity] No table download links found in flash estimate page")
                return None

            # 最初のテーブル（通常はFlash Estimate）を使用
            table_uri = matches[0]
            csv_url = f"{self.ONS_BASE_URL}/download/table?format=csv&uri={table_uri}"
            print(f"[ONS Productivity] Flash estimate CSV URL: {csv_url}")

            # CSVをダウンロード
            csv_response = requests.get(csv_url, headers=headers, timeout=30)
            csv_response.raise_for_status()

            # CSVをパース
            return self._parse_flash_estimate_csv(csv_response.text)

        except Exception as e:
            print(f"[ONS Productivity] Error fetching flash estimate: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_flash_estimate_csv(self, csv_text: str) -> Optional[Dict[str, Any]]:
        """
        Flash Estimate CSVをパース

        CSV形式:
        Period,Output per hour - Quarter versus 2019 level (%),Output per hour - Quarter-on-year ago (%),Output per hour - Quarter-on-quarter (%),Output per worker - Quarter versus 2019 level (%),Output per worker - Quarter-on-year ago (%),Output per worker - Quarter-on-quarter (%)
        2024 Q3,2.0,-1.9,-0.9,2.1,0.1,-0.6
        ...
        """
        try:
            csv_reader = csv.reader(StringIO(csv_text))

            # ヘッダー行をスキップ
            header = next(csv_reader)
            print(f"[ONS Productivity] Flash estimate CSV headers: {header}")

            lzvb_data = []  # Output per hour
            a4ym_data = []  # Output per worker

            for row in csv_reader:
                if len(row) < 7:
                    continue

                try:
                    period_str = row[0].strip()

                    # "YYYY QN" 形式をパース
                    if " Q" not in period_str:
                        continue

                    year_str, quarter_str = period_str.split(" Q")
                    year = int(year_str)
                    quarter = int(quarter_str)

                    # 四半期の最初の月に変換
                    month = (quarter - 1) * 3 + 1
                    date_str = f"{year}-{month:02d}-01"

                    # Output per hour (LZVB相当)
                    # 列インデックス: 1=vs2019, 2=YoY, 3=QoQ
                    lzvb_yoy = float(row[2].strip()) if row[2].strip() else None
                    lzvb_qoq = float(row[3].strip()) if row[3].strip() else None

                    if lzvb_yoy is not None or lzvb_qoq is not None:
                        lzvb_data.append({
                            "date": date_str,
                            "period": period_str,
                            "yoy": lzvb_yoy,
                            "qoq": lzvb_qoq,
                            "is_flash": True,
                        })

                    # Output per worker (A4YM相当)
                    # 列インデックス: 4=vs2019, 5=YoY, 6=QoQ
                    a4ym_yoy = float(row[5].strip()) if row[5].strip() else None
                    a4ym_qoq = float(row[6].strip()) if row[6].strip() else None

                    if a4ym_yoy is not None or a4ym_qoq is not None:
                        a4ym_data.append({
                            "date": date_str,
                            "period": period_str,
                            "yoy": a4ym_yoy,
                            "qoq": a4ym_qoq,
                            "is_flash": True,
                        })

                except (ValueError, IndexError) as e:
                    print(f"[ONS Productivity] Error parsing flash estimate row: {row}, error: {e}")
                    continue

            print(f"[ONS Productivity] Parsed {len(lzvb_data)} flash estimate data points for LZVB")
            print(f"[ONS Productivity] Parsed {len(a4ym_data)} flash estimate data points for A4YM")

            return {
                "lzvb": lzvb_data,
                "a4ym": a4ym_data,
            }

        except Exception as e:
            print(f"[ONS Productivity] Error parsing flash estimate CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _merge_flash_estimate(
        self,
        time_series_data: Dict[str, Any],
        flash_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Time SeriesデータにFlash Estimateをマージ

        マージ戦略:
        - Time Seriesに存在する四半期: Time Seriesのデータを使用
        - Time Seriesに存在しない四半期（速報値）: Flash Estimateを使用

        Args:
            time_series_data: _fetch_all_from_ons() の結果
            flash_data: _fetch_flash_estimate() の結果

        Returns:
            マージされたデータ
        """
        if not flash_data:
            return time_series_data

        result = time_series_data.copy()

        # LZVBのYoYデータにFlash Estimateをマージ
        lzvb_yoy = list(time_series_data.get("lzvb", {}).get("yoy", []))
        lzvb_qoq = list(time_series_data.get("lzvb", {}).get("qoq", []))

        # 既存のTime Series日付を取得
        existing_yoy_dates = {d["date"] for d in lzvb_yoy}
        existing_qoq_dates = {d["date"] for d in lzvb_qoq}

        # Flash EstimateのLZVBデータを追加（Time Seriesに存在しない日付のみ）
        for flash_point in flash_data.get("lzvb", []):
            date = flash_point["date"]

            # YoYデータに追加
            if date not in existing_yoy_dates and flash_point.get("yoy") is not None:
                lzvb_yoy.append({
                    "date": date,
                    "period": flash_point["period"],
                    "yoy": flash_point["yoy"],
                    "is_flash": True,
                })
                print(f"[ONS Productivity] Added flash estimate LZVB YoY for {flash_point['period']}")

            # QoQデータに追加
            if date not in existing_qoq_dates and flash_point.get("qoq") is not None:
                lzvb_qoq.append({
                    "date": date,
                    "period": flash_point["period"],
                    "qoq": flash_point["qoq"],
                    "is_flash": True,
                })
                print(f"[ONS Productivity] Added flash estimate LZVB QoQ for {flash_point['period']}")

        # 日付順にソート
        lzvb_yoy.sort(key=lambda x: x["date"])
        lzvb_qoq.sort(key=lambda x: x["date"])

        # A4YMのYoYデータにFlash Estimateをマージ
        a4ym_yoy = list(time_series_data.get("a4ym", {}).get("yoy", []))
        a4ym_qoq = list(time_series_data.get("a4ym", {}).get("qoq", []))

        existing_yoy_dates = {d["date"] for d in a4ym_yoy}
        existing_qoq_dates = {d["date"] for d in a4ym_qoq}

        for flash_point in flash_data.get("a4ym", []):
            date = flash_point["date"]

            if date not in existing_yoy_dates and flash_point.get("yoy") is not None:
                a4ym_yoy.append({
                    "date": date,
                    "period": flash_point["period"],
                    "yoy": flash_point["yoy"],
                    "is_flash": True,
                })
                print(f"[ONS Productivity] Added flash estimate A4YM YoY for {flash_point['period']}")

            if date not in existing_qoq_dates and flash_point.get("qoq") is not None:
                a4ym_qoq.append({
                    "date": date,
                    "period": flash_point["period"],
                    "qoq": flash_point["qoq"],
                    "is_flash": True,
                })
                print(f"[ONS Productivity] Added flash estimate A4YM QoQ for {flash_point['period']}")

        a4ym_yoy.sort(key=lambda x: x["date"])
        a4ym_qoq.sort(key=lambda x: x["date"])

        # 結果を更新
        result["lzvb"] = {
            **time_series_data.get("lzvb", {}),
            "yoy": lzvb_yoy,
            "qoq": lzvb_qoq,
        }
        result["a4ym"] = {
            **time_series_data.get("a4ym", {}),
            "yoy": a4ym_yoy,
            "qoq": a4ym_qoq,
        }

        return result

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            hours_since_update = (now - last_updated).total_seconds() / 3600

            # 7日以上経過していれば更新
            if hours_since_update >= 24 * 7:
                return True

            # FMPパターンベースの更新判定
            try:
                if should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str, country="GB"):
                    print(f"[ONS Productivity] FMP pattern indicates refresh needed")
                    return True
            except Exception as e:
                print(f"[ONS Productivity] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[ONS Productivity] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ONS Productivity] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ONS Productivity] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ONS Productivity",
            "source": "Office for National Statistics",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "lzvb_count": len(cached_data.get("lzvb", {}).get("data", [])) if cached_data else 0,
            "a4ym_count": len(cached_data.get("a4ym", {}).get("data", [])) if cached_data else 0,
            "dmwo_count": len(cached_data.get("dmwo", {}).get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_productivity_service = ONSProductivityService()
