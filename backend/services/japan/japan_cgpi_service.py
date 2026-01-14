"""
日本 企業物価指数 (CGPI: Corporate Goods Price Index) サービス

BOJ (日本銀行) からCGPIデータを取得

指標:
- 総平均 (Total Average)
- 前年比 (YoY Change %)
- 前月比 (MoM Change %)

データソース:
- BOJ CSV ファイル: https://www.stat-search.boj.or.jp/ssi/mtshtml/csv/pr01_m_1.csv

発表スケジュール:
- 毎月10日〜18日頃 8:50 JST

キャッシュ方式: 独自発表日時ベース判定方式
"""
import json
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "price"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_cgpi_cache.json"


class JapanCGPIService:
    """日本企業物価指数サービス"""

    DATA_CACHE_KEY = "japan:cgpi:data"

    # BOJ CGPI CSV直接URL
    CGPI_CSV_URL = "https://www.stat-search.boj.or.jp/ssi/mtshtml/csv/pr01_m_1.csv"

    # 発表時刻設定（JST）- 8:50 JST
    RELEASE_HOUR_JST = 8
    RELEASE_MINUTE_JST = 50

    def __init__(self):
        pass

    def get_cgpi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """CGPIデータを取得"""
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
        """BOJ CSVファイルからCGPIデータを取得"""
        try:
            print(f"Fetching Japan CGPI data from BOJ CSV: {self.CGPI_CSV_URL}")

            # CSVファイルを直接ダウンロード
            response = requests.get(self.CGPI_CSV_URL, timeout=60)
            response.raise_for_status()

            # Shift-JISでデコード
            csv_content = response.content.decode('shift_jis')
            print(f"Downloaded CSV: {len(response.content)} bytes")

            # CSVをパース
            processed_data = self._parse_cgpi_csv(csv_content)
            if not processed_data:
                return None

            return {"data": processed_data}

        except Exception as e:
            print(f"Error fetching CGPI data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_cgpi_csv(self, csv_content: str) -> Optional[List[Dict[str, Any]]]:
        """
        CGPI CSVファイルをパースして構造化データに変換

        CSV形式:
        - 行0: タイトル「主要時系列統計データ表」
        - 行1: 更新日時
        - 行2: ヘッダー（空, 系列名1, 系列名2, ...）
        - 行3: 系列名称
        - 行4: データコード
        - 行5: 単位
        - 行6: 収録開始期
        - 行7: 収録終了期
        - 行8: 最終更新日
        - 行9以降: データ（日付, 値1, 値2, ...）

        列構成:
        - 列0: 日付 (YYYY/MM形式)
        - 列1: [国内企業物価指数] 総平均（前年比） ← YoY
        - 列5: [国内企業物価指数] 総平均 ← 指数値（MoM計算用）
        """
        try:
            lines = csv_content.strip().split('\n')
            print(f"CSV has {len(lines)} lines")

            # データ行を見つける（行9以降）
            data_start_idx = 9
            data_lines = lines[data_start_idx:]

            # ヘッダー行を確認（デバッグ用）
            if len(lines) > 3:
                header_line = lines[3]
                print(f"Series names: {header_line[:200]}...")

            # データを抽出
            series_data = []
            prev_index = None

            for line in data_lines:
                try:
                    parts = line.split(',')
                    if len(parts) < 6:
                        continue

                    # 日付をパース（YYYY/MM形式）
                    date_str_raw = parts[0].strip()
                    if '/' not in date_str_raw:
                        continue

                    date_parts = date_str_raw.split('/')
                    if len(date_parts) != 2:
                        continue

                    year = date_parts[0]
                    month = date_parts[1].zfill(2)
                    date_str = f"{year}-{month}-01"

                    # YoY（前年比）- 列1
                    yoy_str = parts[1].strip().strip('"')
                    yoy = None
                    if yoy_str and yoy_str != '':
                        try:
                            yoy = round(float(yoy_str), 2)
                        except ValueError:
                            pass

                    # 指数値 - 列5（MoM計算用）
                    index_str = parts[5].strip().strip('"') if len(parts) > 5 else ''
                    index_value = None
                    if index_str and index_str != '':
                        try:
                            index_value = float(index_str)
                        except ValueError:
                            pass

                    # MoMを計算
                    mom = None
                    if index_value is not None and prev_index is not None and prev_index != 0:
                        mom = round(((index_value - prev_index) / prev_index) * 100, 2)

                    prev_index = index_value

                    # YoYまたはMoMがある場合のみ追加
                    if yoy is not None or mom is not None:
                        series_data.append({
                            "date": date_str,
                            "yoy": yoy,
                            "mom": mom,
                        })

                except Exception as e:
                    print(f"Error parsing line: {e}")
                    continue

            # 日付順にソート
            series_data.sort(key=lambda x: x["date"])

            # パフォーマンスのため過去10年分にフィルタ
            if series_data:
                cutoff_year = datetime.now().year - 10
                cutoff_date = f"{cutoff_year}-01-01"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            print(f"Processed CGPI data: {len(series_data)} data points")
            if series_data:
                print(f"Latest data: {series_data[-1]}")

            return series_data

        except Exception as e:
            print(f"Error parsing CGPI CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（発表日時ベース）

        毎月10日〜18日の8:50 JSTを過ぎていて、かつ最終更新がそれより前なら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            today = now.date()

            # 今月の発表期間（10日〜18日）内かどうか
            if 10 <= today.day <= 18:
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
                if 10 <= today.day <= 18:
                    return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を計算

        CGPIは毎月10日〜18日頃に発表
        正確な日付はBOJカレンダーから取得が必要だが、
        ここでは10日を仮の発表日として計算
        """
        try:
            now = datetime.now(JST)
            today = now.date()

            # 今月10日
            this_month_10th = date(today.year, today.month, 10)

            # 今月10日の8:50を過ぎていれば来月
            if today > this_month_10th or (today == this_month_10th and now.hour >= self.RELEASE_HOUR_JST and now.minute >= self.RELEASE_MINUTE_JST):
                # 来月10日
                if today.month == 12:
                    next_release_date = date(today.year + 1, 1, 10)
                else:
                    next_release_date = date(today.year, today.month + 1, 10)
            else:
                next_release_date = this_month_10th

            return {
                "date": next_release_date.strftime("%Y-%m-%d"),
                "datetime_jst": f"{next_release_date.strftime('%Y-%m-%d')}T08:50:00+09:00",
                "label": f"企業物価指数 - {next_release_date.strftime('%Y/%m/%d')} 8:50 JST（予定）"
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
            "indicator": "Japan CGPI (Corporate Goods Price Index)",
            "source": "Bank of Japan (BOJ)",
            "url": self.CGPI_CSV_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
japan_cgpi_service = JapanCGPIService()
