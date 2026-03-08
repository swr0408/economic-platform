"""
台湾PMI先行き（電子工学業）サービス

指標:
- Taiwan PMI Future Outlooks (Electronic & Optical industry)

データソース:
- CIER (Chung-Hua Institution for Economic Research) - PMI Historical Data Excel
- URL: https://www.cier.edu.tw/wp-content/uploads/{year}/{month:02d}/PMI-Historical-Data-Seasonally-Adjusted.xlsx
- シート: Electronic & Optical industry
- ローカルファイル: backend/data/excel/PMI_Historical_Data_Seasonally_Adjusted.xlsx

更新方式:
- 24時間ごとにCIERからExcelをダウンロードして最新日付を比較
- 新しいデータがある場合のみキャッシュを更新
- CIERダウンロード失敗時はローカルExcelをフォールバック

FMPマッピング: なし（S&P Global PMIとは別のサーベイ）
発表スケジュール: 月次（毎月第1営業日、CIERが発表）
"""
import json
import io
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "global" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "taiwan_pmi_outlook_cache.json"

EXCEL_DIR = Path(__file__).parent.parent.parent / "data" / "excel"
EXCEL_FILE = EXCEL_DIR / "PMI_Historical_Data_Seasonally_Adjusted.xlsx"

SHEET_NAME = "Electronic & Optical industry"
DATE_COL = "Unnamed: 0"
VALUE_COL = "Unnamed: 12"  # Future Outlooks

CIER_BASE_URL = "https://www.cier.edu.tw/wp-content/uploads"
CIER_FILENAME = "PMI-Historical-Data-Seasonally-Adjusted.xlsx"


class TaiwanPmiOutlookService:
    """台湾PMI先行き（電子工学業）サービス

    更新ロジック:
    1. Redisキャッシュがあり、24時間以内 → そのまま返す
    2. 24時間経過 → CIERからExcelをダウンロード
    3. ダウンロードしたExcelの最新日付がキャッシュと同じ → キャッシュのlast_updatedだけ更新（チェック済みマーク）
    4. 新しいデータがある → キャッシュを全更新
    """

    DATA_CACHE_KEY = "global:taiwan_pmi_outlook:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """台湾PMI先行きデータを取得"""

        cached_data = redis_client.get(self.DATA_CACHE_KEY)

        if not force_refresh and cached_data:
            last_updated_str = cached_data.get("last_updated")
            if last_updated_str and not self._is_check_due(last_updated_str):
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("latest"),
                    "metadata": cached_data.get("metadata", {}),
                    "next_release": None,
                    "cached": True,
                    "source": "redis",
                    "last_updated": last_updated_str,
                }

        # CIERからExcelダウンロードを試行
        xlsx_content = self._download_from_cier()
        if xlsx_content:
            new_data = self._parse_excel(xlsx_content)
            new_latest = new_data[-1] if new_data else None

            # キャッシュの最新日付と比較
            cached_latest_date = cached_data.get("latest", {}).get("date") if cached_data else None

            if new_latest and new_latest["date"] != cached_latest_date:
                # 新しいデータあり → 全更新
                print(f"[TaiwanPMIOutlook] New data found: {cached_latest_date} -> {new_latest['date']}")
                self._save_local_excel(xlsx_content)
                return self._build_and_cache(new_data, source="cier")
            else:
                # データ変化なし → チェック済みタイムスタンプだけ更新
                print(f"[TaiwanPMIOutlook] No new data (latest: {cached_latest_date}), updating check timestamp")
                if cached_data:
                    cached_data["last_updated"] = datetime.now(JST).isoformat()
                    redis_client.set(self.DATA_CACHE_KEY, cached_data, expire=0)
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": None,
                        "cached": True,
                        "source": "redis",
                        "last_updated": cached_data["last_updated"],
                    }
                # キャッシュなしだがデータはある場合
                if new_data:
                    return self._build_and_cache(new_data, source="cier")

        # CIERダウンロード失敗 → ローカルExcelフォールバック
        local_data = self._load_from_local_excel()
        if local_data:
            local_latest = local_data[-1]
            cached_latest_date = cached_data.get("latest", {}).get("date") if cached_data else None

            if local_latest["date"] != cached_latest_date:
                print(f"[TaiwanPMIOutlook] Local Excel has new data: {cached_latest_date} -> {local_latest['date']}")
                return self._build_and_cache(local_data, source="local_excel")
            elif cached_data:
                # ローカルも変化なし → タイムスタンプ更新のみ
                cached_data["last_updated"] = datetime.now(JST).isoformat()
                redis_client.set(self.DATA_CACHE_KEY, cached_data, expire=0)
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("latest"),
                    "metadata": cached_data.get("metadata", {}),
                    "next_release": None,
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data["last_updated"],
                }

        # キャッシュもローカルもない場合
        if cached_data:
            return {
                "data": cached_data.get("data", []),
                "latest": cached_data.get("latest"),
                "metadata": cached_data.get("metadata", {}),
                "next_release": None,
                "cached": True,
                "source": "redis",
                "last_updated": cached_data.get("last_updated"),
            }

        return {
            "data": [], "latest": None, "metadata": {},
            "next_release": None, "cached": False, "source": "none", "last_updated": None,
        }

    def _build_and_cache(self, data: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
        """データをキャッシュに保存して返す"""
        latest = data[-1] if data else None

        if latest:
            print(f"[TaiwanPMIOutlook] Latest: {latest['date']} value={latest['value']}")

        metadata = {
            "source": "CIER (Chung-Hua Institution for Economic Research)",
            "indicator": "Taiwan PMI Future Outlooks (Electronic & Optical)",
            "description": "台湾PMI先行き（電子工学業）",
            "unit": "index",
            "frequency": "monthly",
        }

        now_str = datetime.now(JST).isoformat()
        cache_payload = {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "next_release": None,
            "last_updated": now_str,
        }
        redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "next_release": None,
            "cached": False,
            "source": source,
            "last_updated": now_str,
        }

    def _download_from_cier(self) -> Optional[bytes]:
        """CIERからExcelファイルをダウンロード

        URLパターン: https://www.cier.edu.tw/wp-content/uploads/{year}/{month:02d}/PMI-Historical-Data-Seasonally-Adjusted.xlsx
        当月 → 前月 → 2ヶ月前 の順に試行
        """
        now = datetime.now(JST)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }

        for offset in range(3):
            dt = now - timedelta(days=offset * 30)
            url = f"{CIER_BASE_URL}/{dt.year}/{dt.month:02d}/{CIER_FILENAME}"
            try:
                print(f"[TaiwanPMIOutlook] Trying CIER download: {url}")
                resp = requests.get(url, headers=headers, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 10000:
                    print(f"[TaiwanPMIOutlook] Downloaded {len(resp.content)} bytes from CIER")
                    return resp.content
            except requests.exceptions.RequestException as e:
                print(f"[TaiwanPMIOutlook] CIER download failed: {e}")

        print("[TaiwanPMIOutlook] All CIER download attempts failed")
        return None

    def _parse_excel(self, xlsx_content: bytes) -> List[Dict[str, Any]]:
        """Excelバイト列をパース"""
        result = []
        try:
            df = pd.read_excel(io.BytesIO(xlsx_content), sheet_name=SHEET_NAME)
            sub = df[[DATE_COL, VALUE_COL]].dropna()

            for _, row in sub.iterrows():
                date_val = row[DATE_COL]
                value_val = row[VALUE_COL]

                try:
                    if isinstance(date_val, datetime):
                        dt = date_val
                    elif isinstance(date_val, pd.Timestamp):
                        dt = date_val.to_pydatetime()
                    else:
                        dt = pd.to_datetime(date_val)

                    if pd.isna(dt):
                        continue

                    date_formatted = dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    continue

                try:
                    value = float(value_val)
                except (ValueError, TypeError):
                    continue

                result.append({
                    "date": date_formatted,
                    "value": round(value, 1),
                })

            print(f"[TaiwanPMIOutlook] Parsed {len(result)} records from Excel")
        except Exception as e:
            print(f"[TaiwanPMIOutlook] Error parsing Excel: {e}")

        return result

    def _load_from_local_excel(self) -> List[Dict[str, Any]]:
        """ローカルExcelファイルから読み込み（フォールバック）"""
        if not EXCEL_FILE.exists():
            print(f"[TaiwanPMIOutlook] Local Excel file not found: {EXCEL_FILE}")
            return []

        try:
            with open(EXCEL_FILE, "rb") as f:
                return self._parse_excel(f.read())
        except Exception as e:
            print(f"[TaiwanPMIOutlook] Error reading local Excel: {e}")
            return []

    def _save_local_excel(self, content: bytes) -> None:
        """ダウンロードしたExcelをローカルに保存"""
        try:
            EXCEL_DIR.mkdir(parents=True, exist_ok=True)
            with open(EXCEL_FILE, "wb") as f:
                f.write(content)
            print(f"[TaiwanPMIOutlook] Saved Excel to {EXCEL_FILE}")
        except Exception as e:
            print(f"[TaiwanPMIOutlook] Failed to save local Excel: {e}")

    def _is_check_due(self, last_updated_str: str) -> bool:
        """CIERへの確認が必要かどうかを判定（24時間経過 or 日跨ぎ6:00以降）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            if (now - last_updated) > timedelta(hours=24):
                return True

            if last_updated.date() < now.date() and now.hour >= 6:
                return True

            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[TaiwanPMIOutlook] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TaiwanPMIOutlook] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        data_count = 0
        latest_date = None
        if cached_data:
            data_count = len(cached_data.get("data", []))
            latest_date = cached_data.get("latest", {}).get("date") if cached_data.get("latest") else None

        return {
            "indicator": "Taiwan PMI Future Outlooks (Electronic & Optical)",
            "source": "CIER (Chung-Hua Institution for Economic Research)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "latest_date": latest_date,
            "data_count": data_count,
            "excel_file_exists": EXCEL_FILE.exists(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
taiwan_pmi_outlook_service = TaiwanPmiOutlookService()
