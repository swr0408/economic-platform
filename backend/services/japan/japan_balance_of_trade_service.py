"""
日本貿易収支サービス（Japan Balance of Trade）
税関貿易統計CSVからデータを取得（通関ベース）

データソース:
- 財務省貿易統計（税関）
- URL: https://www.customs.go.jp/toukei/suii/html/data/d41ma.csv

単位:
- CSVの単位: 千円（a thousand yen）
- 保存・表示: 億円（100 million yen）に変換
- FMP/Investing.comの表示: Billion Yen (B) = 10億円
  - 例: -2741.7B = -27417億円

通関ベース vs 国際収支ベースの違い:
- 通関ベース: 税関を通過した時点で計上、輸入はCIF価格
- 国際収支ベース: 所有権移転時に計上、輸入はFOB価格
- FMP/Investing.comは通関ベースの数値を報告

データ構成:
- 貿易収支 (Trade Balance) = 輸出 - 輸入
- 輸出 (Exports) - Exp-Total
- 輸入 (Imports) - Imp-Total

発表スケジュール:
- 毎月中旬発表（FMPイベント: Balance of Trade）
"""
import csv
import json
import io
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
DATA_CACHE_FILE = CACHE_DIR / "japan_balance_of_trade_cache.json"

# 税関統計CSV URL（世界全体の月次輸出入額）
CUSTOMS_CSV_URL = "https://www.customs.go.jp/toukei/suii/html/data/d41ma.csv"


class JapanBalanceOfTradeService:
    """日本貿易収支サービス（通関ベース）"""

    DATA_CACHE_KEY = "japan:balance_of_trade:data"
    CACHE_TTL = 60 * 60 * 24 * 7  # 7日（FMP発表日ベースで更新判定）

    # FMP indicator ID（マッピングテーブル参照用）
    INDICATOR_ID = "japan_balance_of_trade"

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

    def get_balance_of_trade_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        貿易収支データを取得（通関ベース）

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{
                    "date": "YYYY-MM-DD",
                    "trade_balance": float,  # 億円
                    "exports": float,  # 億円
                    "imports": float   # 億円
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
        api_data = self._fetch_from_customs_csv()

        if api_data:
            latest = api_data[-1] if api_data else None
            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            metadata = {
                "source": "財務省貿易統計（税関）",
                "source_url": CUSTOMS_CSV_URL,
                "description": "Japan Balance of Trade (Customs Basis)",
                "unit": "100 Million Yen (億円)",
                "frequency": "Monthly",
                "basis": "Customs (通関ベース)"
            }

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "metadata": metadata,
                "last_updated": last_updated
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
                "last_updated": last_updated
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

    def _fetch_from_customs_csv(self) -> List[Dict[str, Any]]:
        """税関統計CSVから貿易収支データを取得（通関ベース）"""
        try:
            print(f"Fetching Japan Balance of Trade from Customs CSV: {CUSTOMS_CSV_URL}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(CUSTOMS_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            # Shift_JISでデコード
            content = response.content.decode('shift_jis', errors='replace')

            result = []
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)

            # ヘッダー行を確認（行3: Years/Months,Exp-Total,Imp-Total）
            # データは行5から開始（1979/01から）
            for row in rows[4:]:  # 行5以降がデータ
                if not row or len(row) < 3:
                    continue

                # 日付パース（YYYY/MM形式）
                date_str = row[0].strip()
                if not date_str or '/' not in date_str:
                    continue

                try:
                    parts = date_str.split('/')
                    if len(parts) != 2:
                        continue

                    year = parts[0].strip()
                    month = parts[1].strip().zfill(2)

                    if not year.isdigit() or not month.isdigit():
                        continue

                    formatted_date = f"{year}-{month}-01"

                    # 輸出・輸入を取得（千円単位）
                    exports_str = row[1].strip().replace(' ', '').replace(',', '')
                    imports_str = row[2].strip().replace(' ', '').replace(',', '')

                    if not exports_str or not imports_str:
                        continue

                    # 千円 → 億円に変換（1億円 = 100,000千円）
                    exports_oku = round(float(exports_str) / 100000, 0)
                    imports_oku = round(float(imports_str) / 100000, 0)

                    # 税関CSVには将来月の空枠行（exports=imports=0）が含まれるためスキップ
                    if exports_oku == 0 and imports_oku == 0:
                        continue

                    trade_balance = exports_oku - imports_oku

                    result.append({
                        "date": formatted_date,
                        "trade_balance": trade_balance,
                        "exports": exports_oku,
                        "imports": imports_oku,
                    })

                except (ValueError, IndexError) as e:
                    continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} monthly records from Customs CSV (Japan Balance of Trade)")
            if result:
                latest = result[-1]
                print(f"Latest: {latest['date']} - Trade Balance: {latest['trade_balance']} 億円 ({latest['trade_balance']/10000:.2f}兆円)")

            return result

        except Exception as e:
            print(f"Error fetching Japan Balance of Trade: {e}")
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
japan_balance_of_trade_service = JapanBalanceOfTradeService()
