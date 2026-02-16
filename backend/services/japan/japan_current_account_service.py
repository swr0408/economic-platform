"""
日本経常収支サービス（Japan Current Account）
財務省国際収支統計CSVからデータを取得

データソース:
- 財務省国際収支統計（国際収支の推移）
- URL: https://www.mof.go.jp/policy/international_policy/reference/balance_of_payments/bp_trend/bpnet/sbp/s-1/6s-1-4.csv

単位:
- CSVの単位: 億円（100 million yen）
- 保存・表示: 億円（変換なし）
- FMP/Investing.comの表示と一致

データ構成:
- 経常収支 (Current Account) = 貿易・サービス収支 + 第一次所得収支 + 第二次所得収支
- 貿易・サービス収支 (Goods & Services)
- 第一次所得収支 (Primary Income)
- 第二次所得収支 (Secondary Income)

発表スケジュール:
- 毎月上旬発表（FMPイベント: Current Account）
"""
import csv
import json
import io
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "japan_current_account_cache.json"

# 財務省CSV URL
MOF_CSV_URL = "https://www.mof.go.jp/policy/international_policy/reference/balance_of_payments/bp_trend/bpnet/sbp/s-1/6s-1-4.csv"


class JapanCurrentAccountService:
    """日本経常収支サービス"""

    DATA_CACHE_KEY = "japan:current_account:data"
    CACHE_TTL = 60 * 60 * 24 * 7  # 7日（FMP発表日ベースで更新判定）

    # FMP indicator ID（マッピングテーブル参照用）
    INDICATOR_ID = "japan_current_account"

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
        """FMPから次回発表日時を取得"""
        try:
            return self.fmp_utils["get_next_release"](self.INDICATOR_ID)
        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

    def get_current_account_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        経常収支データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{
                    "date": "YYYY-MM-DD",
                    "current_account": float,  # 10億円
                    "goods_services": float,
                    "primary_income": float,
                    "secondary_income": float
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

        # 外部APIから取得
        api_data = self._fetch_from_mof_csv()

        if api_data:
            latest = api_data[-1] if api_data else None

            metadata = {
                "source": "財務省国際収支統計",
                "source_url": MOF_CSV_URL,
                "description": "Japan Current Account (Balance of Payments)",
                "unit": "100 Million Yen (億円)",
                "frequency": "Monthly"
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

    def _fetch_from_mof_csv(self) -> List[Dict[str, Any]]:
        """財務省CSVから経常収支データを取得"""
        try:
            print(f"Fetching Japan Current Account from MOF CSV: {MOF_CSV_URL}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(MOF_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # Shift_JISでデコード（財務省CSVの文字コード）
            content = response.content.decode('shift_jis', errors='replace')

            result = []
            reader = csv.reader(io.StringIO(content))

            # ヘッダー行を探す
            header_found = False
            current_account_col = None
            goods_services_col = None
            primary_income_col = None
            secondary_income_col = None
            current_year = None  # 年を保持する変数

            # ヘッダー行は複数行に分かれているため、先に全行を読み込んでヘッダーを特定
            rows = list(reader)

            # ヘッダー行を探す（複数行にまたがる）
            data_start_row = 0
            for row_idx, row in enumerate(rows):
                if not row:
                    continue

                row_text = ','.join(row)

                # 経常収支の列を特定（行23付近）
                if '経常収支' in row_text and '(a+b+c)' in row_text:
                    for col_idx, cell in enumerate(row):
                        if '経常収支' in cell and '(a+b+c)' in cell:
                            current_account_col = col_idx
                            break

                # 内訳の列を特定（行25-26付近）- 貿易・サービス収支、第一次所得収支、第二次所得収支
                if '貿易・サービス収支' in row_text or 'Goods & services' in row_text:
                    for col_idx, cell in enumerate(row):
                        cell_text = cell.strip()
                        if '貿易・サービス収支' in cell_text or 'Goods & services' in cell_text:
                            goods_services_col = col_idx
                        elif '第一次所得収支' in cell_text or 'Primary income' in cell_text:
                            primary_income_col = col_idx
                        elif '第二次所得収支' in cell_text or 'Secondary income' in cell_text:
                            secondary_income_col = col_idx

                # データ行の開始位置を特定（年号を含む最初の行）
                if row and len(row) > 0:
                    first_cell = row[0].strip()
                    if '平成' in first_cell or '令和' in first_cell or '昭和' in first_cell:
                        if data_start_row == 0:
                            data_start_row = row_idx
                            header_found = True

            print(f"Header parsing: current_account_col={current_account_col}, goods_services_col={goods_services_col}, primary_income_col={primary_income_col}, secondary_income_col={secondary_income_col}")
            print(f"Data starts at row {data_start_row}")

            if not header_found:
                print("Header not found in CSV")
                return []

            # データ行を処理
            for row_idx, row in enumerate(rows):
                if row_idx < data_start_row:
                    continue

                if not row:
                    continue

                # データ行を解析
                # 日付形式:
                # - "平成8年,1月,1996,Jan,..." - 年の最初の月（西暦年が列2に入る）
                # - ",2月,,Feb,..." - 2月以降（西暦年は空、前の行から引き継ぐ）
                if len(row) < 4:
                    continue

                # 西暦年と月を抽出
                try:
                    year_str = None
                    month_str = None

                    # 列2に西暦年がある場合（年の最初の月）
                    if len(row) > 2 and row[2].strip() and re.match(r'^\d{4}$', row[2].strip()):
                        current_year = row[2].strip()  # 年を更新
                        year_str = current_year
                    elif current_year:
                        # 年がない行は前の年を使用
                        year_str = current_year

                    # 列3に月名（英語）がある
                    if len(row) > 3:
                        month_cell = row[3].strip().replace('(P)', '')  # 速報値マーク除去
                        month_map = {
                            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                        }
                        if month_cell in month_map:
                            month_str = month_map[month_cell]

                    if not year_str or not month_str:
                        continue

                    date_str = f"{year_str}-{month_str}-01"

                    # 値を取得（億円単位のまま保持）
                    # CSVの単位は「億円」（100 million yen）
                    # FMP/Investing.comも億円単位で表示している
                    def parse_value(col_idx):
                        if col_idx is None or col_idx >= len(row):
                            return None
                        val = row[col_idx].strip()
                        # 括弧表記の負数を処理: (1,234) → -1234
                        if val.startswith('(') and val.endswith(')'):
                            val = '-' + val[1:-1]
                        # カンマを除去
                        val = val.replace(',', '').replace('(P)', '').strip()
                        if not val or val == '.':
                            return None
                        try:
                            # 億円単位のまま返す（変換なし）
                            return round(float(val), 0)
                        except ValueError:
                            return None

                    current_account = parse_value(current_account_col)

                    if current_account is not None:
                        data_point = {
                            "date": date_str,
                            "current_account": current_account,
                        }

                        # オプショナルな内訳
                        goods_services = parse_value(goods_services_col)
                        if goods_services is not None:
                            data_point["goods_services"] = goods_services

                        primary_income = parse_value(primary_income_col)
                        if primary_income is not None:
                            data_point["primary_income"] = primary_income

                        secondary_income = parse_value(secondary_income_col)
                        if secondary_income is not None:
                            data_point["secondary_income"] = secondary_income

                        result.append(data_point)

                except (ValueError, IndexError) as e:
                    continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} monthly records from MOF CSV (Japan Current Account)")
            if result:
                latest = result[-1]
                print(f"Latest: {latest['date']} - {latest['current_account']} billion yen")

            return result

        except Exception as e:
            print(f"Error fetching Japan Current Account: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（FMP発表日ベース）
        """
        try:
            return self.fmp_utils["should_refresh"](
                self.INDICATOR_ID,
                last_updated_str
            )
        except Exception as e:
            print(f"Error in _should_refresh: {e}")
            # エラー時は7日以上経過していれば更新
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
japan_current_account_service = JapanCurrentAccountService()
