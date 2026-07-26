"""
日本経常収支対GDP比サービス（Japan Current Account to GDP Ratio）

経常収支（億円）÷ 名目GDP（億円）× 100 で計算

データソース:
- 経常収支: 財務省国際収支統計（月次、億円）
- 名目GDP: 内閣府GDP統計（四半期、10億円→億円変換）

単位:
- 経常収支: 億円（100 million yen）
- 名目GDP: 10億円（billion yen）→ 億円に変換（×10）
- 比率: %（percentage）

計算方法:
- 四半期ごとに経常収支を合計
- 名目GDP四半期値で割って比率を算出
- 年率換算は行わない（四半期フローの比率）

発表スケジュール:
- 経常収支: 毎月上旬発表
- GDP: 四半期ごと発表
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


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_current_account_gdp_ratio_cache.json"

# 内閣府GDP統計CSV URL（名目、季節調整済み、四半期）
# 最新のQE発表URLを使用（2025年3次QE 2次速報）
CAO_GDP_CSV_URL = "https://www.esri.cao.go.jp/jp/sna/data/data_list/sokuhou/files/2025/qe253_2/tables/gaku-mk2532.csv"


class JapanCurrentAccountGdpRatioService:
    """日本経常収支対GDP比サービス"""

    DATA_CACHE_KEY = "japan:current_account_gdp_ratio:data"
    CACHE_TTL = 60 * 60 * 24 * 7  # 7日

    # FMP indicator ID（マッピングテーブル参照用）
    INDICATOR_ID = "japan_current_account_gdp_ratio"

    def __init__(self):
        self._fmp_utils = None

    @property
    def fmp_utils(self):
        """遅延インポートでFMPユーティリティを取得"""
        if self._fmp_utils is None:
            from services.japan.fmp_next_release_utils import (
                get_next_release_from_fmp,
                should_refresh_by_fmp_schedule
            )
            self._fmp_utils = {
                "get_next_release": get_next_release_from_fmp,
                "should_refresh": should_refresh_by_fmp_schedule
            }
        return self._fmp_utils

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日時を取得（GDPベース）"""
        try:
            # GDPの発表日をベースにする
            # (マッピングIDは indicator_event_mapping に実在する japan_gdp_qoq を使う。
            #  旧 "quarterly_gdp" はマッピング行が無く常に None → TTLフォールバックだった)
            return self.fmp_utils["get_next_release"]("japan_gdp_qoq")
        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

    def get_current_account_gdp_ratio_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        経常収支対GDP比データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{
                    "date": "YYYY-QN",
                    "ratio": float,  # %
                    "current_account": float,  # 億円（四半期合計）
                    "nominal_gdp": float  # 億円
                }, ...],
                "latest": {...},
                "metadata": {...},
                "next_release": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
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
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=self.CACHE_TTL)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # データを計算
        api_data = self._calculate_ratio()

        if api_data:
            latest = api_data[-1] if api_data else None

            metadata = {
                "source": "財務省国際収支統計 / 内閣府GDP統計",
                "description": "Japan Current Account to GDP Ratio",
                "unit": "Percentage (%)",
                "frequency": "Quarterly",
                "calculation": "Current Account (quarterly sum) / Nominal GDP × 100"
            }

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat()
            }

            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=self.CACHE_TTL)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "metadata": metadata,
                "next_release": self._get_next_release(),
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": self._get_next_release(),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": self._get_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _calculate_ratio(self) -> List[Dict[str, Any]]:
        """経常収支対GDP比を計算"""
        try:
            # 経常収支データを取得
            from services.japan.japan_current_account_service import japan_current_account_service
            ca_response = japan_current_account_service.get_current_account_data()
            ca_data = ca_response.get("data", [])

            if not ca_data:
                print("No current account data available")
                return []

            # 名目GDPデータを取得
            gdp_data = self._fetch_nominal_gdp()

            if not gdp_data:
                print("No nominal GDP data available")
                return []

            # 経常収支を四半期ごとに合計
            ca_quarterly = self._aggregate_ca_to_quarterly(ca_data)

            # 比率を計算
            result = []
            for quarter, ca_sum in ca_quarterly.items():
                if quarter in gdp_data:
                    gdp_value = gdp_data[quarter]
                    if gdp_value > 0:
                        # 比率 = 経常収支（億円）÷ GDP（億円）× 100
                        ratio = (ca_sum / gdp_value) * 100
                        result.append({
                            "date": quarter,
                            "ratio": round(ratio, 2),
                            "current_account": ca_sum,
                            "nominal_gdp": gdp_value
                        })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"Calculated {len(result)} quarterly ratios")
            if result:
                latest = result[-1]
                print(f"Latest: {latest['date']} - {latest['ratio']}%")

            return result

        except Exception as e:
            print(f"Error calculating ratio: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_nominal_gdp(self) -> Dict[str, float]:
        """内閣府CSVから名目GDPデータを取得"""
        try:
            print(f"Fetching Nominal GDP from CAO CSV: {CAO_GDP_CSV_URL}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(CAO_GDP_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # Shift_JISでデコード
            content = response.content.decode('shift_jis', errors='replace')

            result = {}
            lines = content.split('\n')

            # 現在の年を保持（Q2-Q4は年が省略されるため）
            current_year = None

            # データ行を処理（行7から開始）
            for line in lines[7:]:
                if not line.strip():
                    continue

                # CSVをパース（カンマ区切り、引用符内のカンマに注意）
                parts = self._parse_csv_line(line)
                if len(parts) < 2:
                    continue

                # 日付部分をパース
                date_part = parts[0].strip().strip('"')

                # パターン1: "1994/ 1- 3." （Q1、年を含む）
                match = re.match(r'(\d{4})/\s*(\d+)-\s*(\d+)\.?', date_part)
                if match:
                    current_year = int(match.group(1))
                    start_month = int(match.group(2))
                else:
                    # パターン2: "4- 6." （Q2-Q4、年を省略）
                    match = re.match(r'(\d+)-\s*(\d+)\.?', date_part)
                    if match and current_year:
                        start_month = int(match.group(1))
                    else:
                        continue

                # 四半期を判定
                if start_month == 1:
                    quarter = f"{current_year}-Q1"
                elif start_month == 4:
                    quarter = f"{current_year}-Q2"
                elif start_month == 7:
                    quarter = f"{current_year}-Q3"
                elif start_month == 10:
                    quarter = f"{current_year}-Q4"
                else:
                    continue

                # GDP値をパース（列1、10億円単位）
                gdp_str = parts[1].strip().strip('"').replace(',', '')
                try:
                    gdp_billion = float(gdp_str)
                    # 10億円 → 億円に変換（×10）
                    gdp_oku = gdp_billion * 10
                    result[quarter] = gdp_oku
                except (ValueError, IndexError):
                    continue

            print(f"Fetched {len(result)} quarterly GDP records")
            return result

        except Exception as e:
            print(f"Error fetching nominal GDP: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _parse_csv_line(self, line: str) -> List[str]:
        """CSVライン（引用符対応）をパース"""
        result = []
        current = ""
        in_quotes = False

        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                result.append(current)
                current = ""
            else:
                current += char

        result.append(current)
        return result

    def _aggregate_ca_to_quarterly(self, ca_data: List[Dict]) -> Dict[str, float]:
        """月次経常収支を四半期合計に変換"""
        quarterly = {}

        for item in ca_data:
            date_str = item.get("date", "")
            ca_value = item.get("current_account")

            if not date_str or ca_value is None:
                continue

            # YYYY-MM-DD → YYYY-QN
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                year = dt.year
                month = dt.month

                if month in [1, 2, 3]:
                    quarter = f"{year}-Q1"
                elif month in [4, 5, 6]:
                    quarter = f"{year}-Q2"
                elif month in [7, 8, 9]:
                    quarter = f"{year}-Q3"
                else:
                    quarter = f"{year}-Q4"

                if quarter not in quarterly:
                    quarterly[quarter] = 0
                quarterly[quarter] += ca_value

            except ValueError:
                continue

        return quarterly

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return self.fmp_utils["should_refresh"](
                "japan_gdp_qoq",  # GDPの発表スケジュールに従う（実在するマッピングID）
                last_updated_str
            )
        except Exception as e:
            print(f"Error in _should_refresh: {e}")
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                return (now - last_updated).days >= 7
            except Exception:
                return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator_id": self.INDICATOR_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
japan_current_account_gdp_ratio_service = JapanCurrentAccountGdpRatioService()
