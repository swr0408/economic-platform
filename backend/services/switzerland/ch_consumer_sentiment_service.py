"""
SECO消費者景況感サービス
SECO（スイス連邦経済省経済事務局）から消費者景況感データを取得

指標:
- SECO Consumer Climate（SECO消費者景況感）
- スイスの消費者信頼感指数

データソース:
- SECO（State Secretariat for Economic Affairs）
- 過去時系列: https://www.seco.admin.ch/dam/seco/en/dokumente/Wirtschaft/Wirtschaftslage/Konsumentenstimmung/ks_q.xlsx.download.xlsx/ks_q.xlsx
- 最新月次: https://www.seco.admin.ch/dam/seco/en/dokumente/Wirtschaft/Wirtschaftslage/Konsumentenstimmung/ks_m.xlsx.download.xlsx/ks_m.xlsx

発表スケジュール:
- 不定期（FMPカレンダーから取得）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.switzerland.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_consumer_sentiment_cache.json"


class CHConsumerSentimentService:
    """SECO消費者景況感サービス"""

    DATA_CACHE_KEY = "switzerland:ch_consumer_sentiment:data"
    ECONALPHA_ID = "ch_consumer_sentiment"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERN = "SECO Consumer Climate"

    # SECO API URLs (恒常的に HTTP 502 のためフォールバック扱い)
    QUARTERLY_URL = "https://www.seco.admin.ch/dam/seco/en/dokumente/Wirtschaft/Wirtschaftslage/Konsumentenstimmung/ks_q.xlsx.download.xlsx/ks_q.xlsx"
    MONTHLY_URL = "https://www.seco.admin.ch/dam/seco/en/dokumente/Wirtschaft/Wirtschaftslage/Konsumentenstimmung/ks_m.xlsx.download.xlsx/ks_m.xlsx"

    # SNB データポータルが SECO 消費者景況感を machine-readable CSV で再配信している。
    # NIK 系列 = 総合指数 (Konsumentenstimmungsindex)。
    # conconm = 月次 (2023-01〜)、concon = 四半期 (1972-Q4〜) で履歴を補完する。
    SNB_MONTHLY_URL = "https://data.snb.ch/api/cube/conconm/data/csv/en"
    SNB_QUARTERLY_URL = "https://data.snb.ch/api/cube/concon/data/csv/en"

    def __init__(self):
        pass

    def get_consumer_sentiment_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """SECO消費者景況感データを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)

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
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # まず安定した SNB 再配信 CSV、ダメなら従来の SECO xlsx にフォールバック
        seco_result = self._load_from_snb() or self._load_from_seco()
        if seco_result:
            # 最新値を取得
            latest = seco_result[-1] if seco_result else None

            cache_payload = {
                "data": seco_result,
                "latest": latest,
                "metadata": {
                    "source": "SECO (State Secretariat for Economic Affairs)",
                    "indicator": "Consumer Climate",
                    "description": "スイス消費者景況感指数",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": seco_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "seco_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _parse_snb_nik(self, url: str, quarterly: bool) -> List[Dict[str, Any]]:
        """SNB CSV cube から NIK 系列を [{date:"YYYY-MM-01", value}] で取得。

        CSV 形式: 先頭にメタ行 (CubeId, PublishingDate) → "Date";"D0";"Value" → データ行。
        月次 Date="YYYY-MM"、四半期 Date="YYYY-Qn" (Q1→01,Q2→04,Q3→07,Q4→10 に変換)。
        """
        import re
        q_map = {"Q1": "01", "Q2": "04", "Q3": "07", "Q4": "10"}
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        out: List[Dict[str, Any]] = []
        for line in resp.text.splitlines():
            parts = [p.strip().strip('"') for p in line.split(";")]
            if len(parts) < 3 or parts[1] != "NIK":
                continue
            date_raw, value = parts[0], parts[2]
            if quarterly:
                m = re.match(r"^(\d{4})-(Q[1-4])$", date_raw)
                if not m:
                    continue
                date_str = f"{m.group(1)}-{q_map[m.group(2)]}-01"
            else:
                if not re.match(r"^\d{4}-\d{2}$", date_raw):
                    continue
                date_str = f"{date_raw}-01"
            try:
                out.append({"date": date_str, "value": round(float(value), 1)})
            except ValueError:
                continue
        out.sort(key=lambda x: x["date"])
        return out

    def _load_from_snb(self) -> List[Dict[str, Any]]:
        """SNB の CSV cube から SECO 消費者景況感を取得 (四半期履歴 + 月次最新を結合)。

        SECO 自身の xlsx は恒常 502 のため、安定した SNB の machine-readable CSV を主ソースにする。
        Returns: [{"date": "YYYY-MM-01", "value": float}, ...] (日付昇順)
        """
        try:
            print(f"[CHConsumerSentiment] Fetching from SNB: {self.SNB_MONTHLY_URL} (+ quarterly)")
            monthly = self._parse_snb_nik(self.SNB_MONTHLY_URL, quarterly=False)
            try:
                quarterly = self._parse_snb_nik(self.SNB_QUARTERLY_URL, quarterly=True)
            except Exception as qe:
                print(f"[CHConsumerSentiment] SNB quarterly fetch failed: {qe}")
                quarterly = []

            # 月次開始日より前は四半期、それ以降は月次 (元の SECO 結合ロジックと同じ)
            if monthly and quarterly:
                monthly_min = min(d["date"] for d in monthly)
                combined = [d for d in quarterly if d["date"] < monthly_min] + monthly
            else:
                combined = monthly or quarterly
            combined.sort(key=lambda x: x["date"])
            print(f"[CHConsumerSentiment] Loaded {len(combined)} records from SNB "
                  f"(quarterly={len(quarterly)}, monthly={len(monthly)})")
            return combined
        except Exception as e:
            print(f"[CHConsumerSentiment] Error loading from SNB: {e}")
            return []

    def _load_from_seco(self) -> List[Dict[str, Any]]:
        """SECOからデータを取得（四半期と月次を組み合わせ）"""
        try:
            # 四半期データを取得
            quarterly_data = self._fetch_quarterly_data()
            print(f"[CHConsumerSentiment] Quarterly data: {len(quarterly_data)} records")

            # 月次データを取得
            monthly_data = self._fetch_monthly_data()
            print(f"[CHConsumerSentiment] Monthly data: {len(monthly_data)} records")

            if not quarterly_data and not monthly_data:
                return []

            # 月次データの最古日付を取得
            monthly_min_date = None
            if monthly_data:
                monthly_min_date = min(d["date"] for d in monthly_data)
                print(f"[CHConsumerSentiment] Monthly data starts from: {monthly_min_date}")

            # 四半期データから月次データの最古日付より前のものを抽出
            combined = []
            if quarterly_data and monthly_min_date:
                for item in quarterly_data:
                    if item["date"] < monthly_min_date:
                        combined.append(item)
                print(f"[CHConsumerSentiment] Quarterly records before monthly: {len(combined)}")
            elif quarterly_data and not monthly_data:
                combined = quarterly_data

            # 月次データを追加
            combined.extend(monthly_data)

            # 日付でソート
            combined.sort(key=lambda x: x["date"])

            print(f"[CHConsumerSentiment] Total combined records: {len(combined)}")
            if combined:
                print(f"[CHConsumerSentiment] Date range: {combined[0]['date']} to {combined[-1]['date']}")
                print(f"[CHConsumerSentiment] Latest: value={combined[-1].get('value')}")

            return combined

        except Exception as e:
            print(f"[CHConsumerSentiment] Error loading from SECO: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_quarterly_data(self) -> List[Dict[str, Any]]:
        """四半期データを取得"""
        try:
            print(f"[CHConsumerSentiment] Fetching quarterly data: {self.QUARTERLY_URL}")

            resp = requests.get(self.QUARTERLY_URL, timeout=60)
            resp.raise_for_status()

            excel_data = io.BytesIO(resp.content)
            # data_csaシートを読む（季節調整済みデータ）
            df = pd.read_excel(excel_data, sheet_name='data_csa')

            # カラム名を確認（最初の5つ）
            print(f"[CHConsumerSentiment] Quarterly columns: {list(df.columns)[:5]}")

            result = []
            current_date = datetime.now(JST).date()

            # 最初のカラムが年、2番目が四半期、3番目がIndex（ks_i63_index_q）
            year_col = df.columns[0]  # Konsumentenstimmung（年）
            quarter_col = df.columns[1]  # Unnamed: 1（四半期）
            index_col = df.columns[2]  # Unnamed: 2（ks_i63_index_q）

            for _, row in df.iterrows():
                year_val = row[year_col]
                quarter_val = row[quarter_col]
                index_val = row[index_col]

                # 数値の年と四半期のみ処理
                if pd.isna(year_val) or pd.isna(quarter_val) or pd.isna(index_val):
                    continue

                try:
                    year = int(year_val)
                    quarter = int(quarter_val)
                except (ValueError, TypeError):
                    continue

                # 四半期から月を決定
                quarter_month_map = {1: '01', 2: '04', 3: '07', 4: '10'}
                if quarter not in quarter_month_map:
                    continue

                date_formatted = f"{year}-{quarter_month_map[quarter]}-01"

                # 未来のデータはスキップ
                try:
                    date_obj = datetime.strptime(date_formatted, "%Y-%m-%d").date()
                    if date_obj > current_date:
                        continue
                except ValueError:
                    continue

                result.append({
                    "date": date_formatted,
                    "value": round(float(index_val), 1),
                })

            print(f"[CHConsumerSentiment] Quarterly records: {len(result)}")
            return result

        except Exception as e:
            print(f"[CHConsumerSentiment] Error fetching quarterly data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_monthly_data(self) -> List[Dict[str, Any]]:
        """月次データを取得"""
        try:
            print(f"[CHConsumerSentiment] Fetching monthly data: {self.MONTHLY_URL}")

            resp = requests.get(self.MONTHLY_URL, timeout=60)
            resp.raise_for_status()

            excel_data = io.BytesIO(resp.content)
            # data_naシートを読む（非季節調整だが月次データ）
            df = pd.read_excel(excel_data, sheet_name='data_na')

            # カラム名を確認（最初の5つ）
            print(f"[CHConsumerSentiment] Monthly columns: {list(df.columns)[:5]}")

            result = []
            current_date = datetime.now(JST).date()

            # 最初のカラムが年、2番目が月、3番目がIndex（ks_i63_index_m）
            year_col = df.columns[0]  # Konsumentenstimmung（年）
            month_col = df.columns[1]  # Unnamed: 1（月）
            index_col = df.columns[2]  # Unnamed: 2（ks_i63_index_m）

            for _, row in df.iterrows():
                year_val = row[year_col]
                month_val = row[month_col]
                index_val = row[index_col]

                # 数値の年と月のみ処理
                if pd.isna(year_val) or pd.isna(month_val) or pd.isna(index_val):
                    continue

                try:
                    year = int(year_val)
                    month = int(month_val)
                except (ValueError, TypeError):
                    continue

                # 月が1-12の範囲内かチェック
                if month < 1 or month > 12:
                    continue

                date_formatted = f"{year}-{month:02d}-01"

                # 未来のデータはスキップ
                try:
                    date_obj = datetime.strptime(date_formatted, "%Y-%m-%d").date()
                    if date_obj > current_date:
                        continue
                except ValueError:
                    continue

                result.append({
                    "date": date_formatted,
                    "value": round(float(index_val), 1),
                })

            print(f"[CHConsumerSentiment] Monthly records: {len(result)}")
            return result

        except Exception as e:
            print(f"[CHConsumerSentiment] Error fetching monthly data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_date(self, date_val: Any, is_quarterly: bool = False) -> Optional[str]:
        """日付を解析してYYYY-MM-DD形式に変換"""
        try:
            if pd.isna(date_val):
                return None

            # pandasのTimestamp
            if isinstance(date_val, pd.Timestamp):
                return date_val.strftime("%Y-%m-01")

            # datetimeオブジェクト
            if isinstance(date_val, datetime):
                return date_val.strftime("%Y-%m-01")

            # 文字列
            date_str = str(date_val).strip()

            # "YYYY-MM" 形式
            if len(date_str) == 7 and date_str[4] == '-':
                return f"{date_str}-01"

            # "YYYY-MM-DD" 形式
            if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
                # 月初に正規化
                return f"{date_str[:7]}-01"

            # "YYYYQ1" 形式（四半期）
            if 'Q' in date_str.upper():
                parts = date_str.upper().replace('Q', ' Q').split()
                if len(parts) >= 2:
                    year = parts[0]
                    quarter = parts[1]
                    quarter_month_map = {'Q1': '01', 'Q2': '04', 'Q3': '07', 'Q4': '10'}
                    if quarter in quarter_month_map:
                        return f"{year}-{quarter_month_map[quarter]}-01"

            # "YYYY Qn" 形式
            if ' ' in date_str:
                parts = date_str.split()
                if len(parts) == 2:
                    year = parts[0]
                    q = parts[1].upper()
                    quarter_month_map = {'Q1': '01', 'Q2': '04', 'Q3': '07', 'Q4': '10'}
                    if q in quarter_month_map:
                        return f"{year}-{quarter_month_map[q]}-01"

            return None

        except Exception as e:
            print(f"[CHConsumerSentiment] Date parse error for {date_val}: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CHConsumerSentiment] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHConsumerSentiment] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "SECO Consumer Climate",
            "source": "SECO (State Secretariat for Economic Affairs)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_consumer_sentiment_service = CHConsumerSentimentService()
