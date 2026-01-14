"""
日本 企業向けサービス価格指数 (SPPI: Services Producer Price Index) サービス

BOJ (日本銀行) からSPPIデータを取得

指標:
- 総平均 (Total Average)
- 前年比 (YoY Change %)

データソース:
- BOJ ZIP ファイル: https://www.stat-search.boj.or.jp/ssi/docs/info/sppi_m_jp.zip

発表スケジュール:
- 毎月22日〜28日頃 8:50 JST

キャッシュ方式: 独自発表日時ベース判定方式
"""
import json
import os
import requests
import zipfile
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "price"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_sppi_cache.json"
TEMP_DIR = CACHE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class JapanSPPIService:
    """日本企業向けサービス価格指数サービス"""

    DATA_CACHE_KEY = "japan:sppi:data"

    # BOJ SPPI データURL
    SPPI_ZIP_URL = "https://www.stat-search.boj.or.jp/ssi/docs/info/sppi_m_jp.zip"

    # 発表時刻設定（JST）- 8:50 JST
    RELEASE_HOUR_JST = 8
    RELEASE_MINUTE_JST = 50

    def __init__(self):
        pass

    def get_sppi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """SPPIデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    cached_data["cached"] = True
                    cached_data["source"] = "redis"
                    cached_data["next_release"] = self._calculate_next_release()
                    return cached_data

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    file_cache["cached"] = True
                    file_cache["source"] = "file"
                    file_cache["next_release"] = self._calculate_next_release()
                    return file_cache

        # BOJからデータ取得
        result = self._fetch_from_boj()
        if result and result.get("data"):
            latest = result["data"][-1] if result["data"] else None
            next_release = self._calculate_next_release()

            cache_payload = {
                "data": result["data"],
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result["data"],
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "boj",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            file_cache["cached"] = True
            file_cache["source"] = "file (fallback)"
            file_cache["next_release"] = self._calculate_next_release()
            return file_cache

        return {
            "data": [],
            "latest": None,
            "next_release": self._calculate_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_boj(self) -> Optional[Dict[str, Any]]:
        """BOJ ZIPファイルからSPPIデータを取得"""
        try:
            print("Fetching Japan SPPI data from BOJ ZIP file")

            # ZIPファイルをダウンロード
            csv_path = self._download_and_extract_zip()
            if not csv_path:
                return None

            # CSVをパース
            processed_data = self._parse_sppi_csv(csv_path)
            if not processed_data:
                return None

            # 一時ファイルをクリーンアップ
            self._cleanup_temp_files()

            return {"data": processed_data}

        except Exception as e:
            print(f"Error fetching SPPI data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _download_and_extract_zip(self) -> Optional[Path]:
        """ZIPファイルをダウンロードして展開"""
        try:
            print(f"Downloading SPPI data from {self.SPPI_ZIP_URL}")

            response = requests.get(self.SPPI_ZIP_URL, timeout=60)
            response.raise_for_status()

            # ZIPファイルを保存
            zip_path = TEMP_DIR / "sppi_m_jp.zip"
            zip_path.write_bytes(response.content)

            print(f"Downloaded {len(response.content)} bytes")

            # ZIPファイルを展開
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                print(f"ZIP contains {len(file_list)} files: {file_list}")
                zip_ref.extractall(TEMP_DIR)

            # CSVまたはTXTファイルを探す
            extracted_files = list(TEMP_DIR.glob("*.csv")) + list(TEMP_DIR.glob("*.txt"))

            if not extracted_files:
                print("No CSV or TXT files found in ZIP")
                return None

            # 最大のファイルを使用
            data_file = max(extracted_files, key=lambda p: p.stat().st_size)
            print(f"Using data file: {data_file.name}")

            return data_file

        except Exception as e:
            print(f"Error downloading/extracting SPPI data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_sppi_csv(self, csv_path: Path) -> Optional[List[Dict[str, Any]]]:
        """SPPI CSVファイルをパースして構造化データに変換"""
        try:
            print(f"Parsing SPPI CSV file: {csv_path}")

            # 日本語のエンコーディングを試行
            encodings = ['shift_jis', 'cp932', 'utf-8']
            df = None

            for encoding in encodings:
                try:
                    df = pd.read_csv(csv_path, encoding=encoding)
                    print(f"Successfully read CSV with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue

            if df is None:
                print("Failed to read CSV with any encoding")
                return None

            print(f"CSV shape: {df.shape}")
            print(f"CSV columns: {df.columns.tolist()[:5]}...")

            # データを処理
            processed_data = self._process_sppi_dataframe(df)

            return processed_data

        except Exception as e:
            print(f"Error parsing SPPI CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_sppi_dataframe(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        SPPI DataFrameを処理して構造化フォーマットに変換

        CSV形式:
        - 1列目: シリーズコード (例: PRCS20_5200000000)
        - 2列目: 説明
        - 3列目: カテゴリ名
        - 残りの列: YYYYMM形式の日付列と値
        """
        try:
            print(f"Processing SPPI dataframe with shape: {df.shape}")

            # 列名を取得 - 最初の3列はメタデータ、残りは日付
            columns = df.columns.tolist()
            date_columns = [col for col in columns[3:] if isinstance(col, str) and str(col).isdigit() and len(str(col)) == 6]

            print(f"Found {len(date_columns)} date columns")

            if not date_columns:
                print("No date columns found in CSV")
                return []

            # 総平均 (Total Average) の行を探す
            # シリーズコード PRCS20_5200000000 または カテゴリ名「総平均」
            total_avg_row = None
            for idx, row in df.iterrows():
                series_code = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                category_name = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ""

                if "5200000000" in series_code or "総平均" in category_name:
                    total_avg_row = row
                    print(f"Found total average series: {series_code}")
                    break

            if total_avg_row is None:
                print("Could not find total average (総平均) series, using first row")
                total_avg_row = df.iloc[0]

            # 総平均行からデータポイントを抽出
            series_data = []
            for date_col in date_columns:
                try:
                    # YYYYMM形式から日付をパース
                    date_str_raw = str(date_col)
                    year = date_str_raw[:4]
                    month = date_str_raw[4:6]
                    date_str = f"{year}-{month}-01"

                    # 値を取得
                    value = total_avg_row[date_col]

                    # NaNや無効な値をスキップ
                    if pd.isna(value):
                        continue

                    # floatに変換
                    if isinstance(value, str):
                        value = value.strip()
                        if not value or value == '':
                            continue
                        value = float(value)
                    else:
                        value = float(value)

                    series_data.append({
                        "date": date_str,
                        "index": round(value, 2),
                        "yoy": None  # 後で計算
                    })
                except Exception as e:
                    print(f"Error processing date {date_col}: {e}")
                    continue

            # 日付順にソート
            series_data.sort(key=lambda x: x["date"])

            # 前年比 (YoY) を計算
            for i in range(len(series_data)):
                current_date = series_data[i]["date"]
                current_value = series_data[i]["index"]

                # 12ヶ月前のデータを探す
                year_ago_date = f"{int(current_date[:4]) - 1}{current_date[4:]}"

                for j in range(len(series_data)):
                    if series_data[j]["date"] == year_ago_date:
                        year_ago_value = series_data[j]["index"]
                        if year_ago_value and year_ago_value != 0:
                            yoy_change = ((current_value - year_ago_value) / year_ago_value) * 100
                            series_data[i]["yoy"] = round(yoy_change, 2)
                        break

            # パフォーマンスのため過去5年分にフィルタ
            if series_data:
                cutoff_year = datetime.now().year - 5
                cutoff_date = f"{cutoff_year}-01-01"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            print(f"Processed SPPI data: {len(series_data)} data points")
            return series_data

        except Exception as e:
            print(f"Error processing SPPI dataframe: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _cleanup_temp_files(self):
        """一時ファイルをクリーンアップ"""
        try:
            for file in TEMP_DIR.glob("*"):
                if file.is_file():
                    file.unlink()
        except Exception as e:
            print(f"Error cleaning up temp files: {e}")

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（発表日時ベース）

        毎月22日〜28日の8:50 JSTを過ぎていて、かつ最終更新がそれより前なら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            today = now.date()

            # 今月の発表期間（22日〜28日）内かどうか
            if 22 <= today.day <= 28:
                # 発表時刻（8:50 JST）
                release_time = datetime(
                    today.year, today.month, today.day,
                    self.RELEASE_HOUR_JST, self.RELEASE_MINUTE_JST,
                    tzinfo=JST
                )

                # 発表時刻を過ぎている場合
                if now >= release_time:
                    # 最終更新が今日の発表時刻より前なら更新が必要
                    if last_updated < release_time:
                        return True

            # キャッシュが1日以上古い場合も更新
            if (now - last_updated).days >= 1:
                # 発表期間内なら更新
                if 22 <= today.day <= 28:
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を計算

        SPPIは毎月22日〜28日頃に発表
        正確な日付はBOJカレンダーから取得が必要だが、
        ここでは22日を仮の発表日として計算
        """
        try:
            now = datetime.now(JST)
            today = now.date()

            # 今月22日
            this_month_22nd = date(today.year, today.month, 22)

            # 今月22日の8:50を過ぎていれば来月
            if today > this_month_22nd or (today == this_month_22nd and now.hour >= self.RELEASE_HOUR_JST and now.minute >= self.RELEASE_MINUTE_JST):
                # 来月22日
                if today.month == 12:
                    next_release_date = date(today.year + 1, 1, 22)
                else:
                    next_release_date = date(today.year, today.month + 1, 22)
            else:
                next_release_date = this_month_22nd

            return {
                "date": next_release_date.strftime("%Y-%m-%d"),
                "datetime_jst": f"{next_release_date.strftime('%Y-%m-%d')}T08:50:00+09:00",
                "label": f"企業向けサービス価格指数 - {next_release_date.strftime('%Y/%m/%d')} 8:50 JST（予定）"
            }

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Japan SPPI (Services Producer Price Index)",
            "source": "Bank of Japan (BOJ)",
            "url": self.SPPI_ZIP_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
japan_sppi_service = JapanSPPIService()
