"""
NZ PMI/PSI/PCIサービス

指標:
- PMI: BusinessNZ Manufacturing PMI（製造業PMI）
- PSI: BusinessNZ Performance of Services Index（サービス業PSI）
- PCI: BusinessNZ/BNZ Performance of Composite Index（総合PCI）

データソース:
- Excel時系列データ（BusinessNZ公開）
  PMI: https://businessnz.org.nz/__data/assets/excel_doc/0003/73875/PMI-Time-Series-Data.xls?v=5.2
  PSI: https://businessnz.org.nz/__data/assets/excel_doc/0008/73916/PSI-Time-Series-Data.xls?v=5.2
  PCI: https://businessnz.org.nz/__data/assets/excel_doc/0009/73917/PCI-Time-Series-Data.xls?v=5.2
- DB蓄積 (economic_calendar_events)
- FMP API（最新値・前回値修正）

FMPマッピング:
- Business NZ PMI (econalpha_id: nz_pmi)
- Services NZ PSI (econalpha_id: nz_psi)
- Composite NZ PCI (econalpha_id: nz_pci)

発表スケジュール: 月次（PMI/PSI/PCIは別々の日に発表）
"""
import io
import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import requests

from core.database import SessionLocal
from core.redis_client import redis_client
from services.calendar.fmp_service import fmp_service
from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern
from sqlalchemy import text


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
AUCKLAND = ZoneInfo("Pacific/Auckland")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PMI_CACHE_FILE = CACHE_DIR / "nz_pmi_cache.json"
PSI_CACHE_FILE = CACHE_DIR / "nz_psi_cache.json"
PCI_CACHE_FILE = CACHE_DIR / "nz_pci_cache.json"

# ExcelファイルURL
PMI_URL = "https://businessnz.org.nz/__data/assets/excel_doc/0003/73875/PMI-Time-Series-Data.xls?v=5.2"
PSI_URL = "https://businessnz.org.nz/__data/assets/excel_doc/0008/73916/PSI-Time-Series-Data.xls?v=5.2"
PCI_URL = "https://businessnz.org.nz/__data/assets/excel_doc/0009/73917/PCI-Time-Series-Data.xls?v=5.2"

# FMPパターン（各指標別）
PMI_FMP_PATTERN = "Business NZ PMI"
PSI_FMP_PATTERN = "Services NZ PSI"
PCI_FMP_PATTERN = "Composite NZ PCI"
FMP_COUNTRY = "NZ"

# Excelシート・列設定
# SA（季節調整済み）シートを使用
# PMI: "Seasonally Adjusted" シート、Row 1がヘッダー、Row 2からデータ、Col0=日付, Col1=PMI
# PSI: "PSI Seasonally Adjusted" シート、同様の構造
# PCI: "Combined Seasonally Adjusted" シート、Col1=GDP Weighted Combined Index

EXCEL_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
}


class NzPmiService:
    """NZ PMI/PSI/PCIサービス（Excel + DB + FMP方式）"""

    PMI_CACHE_KEY = "newzealand:nz_pmi:data"
    PSI_CACHE_KEY = "newzealand:nz_psi:data"
    PCI_CACHE_KEY = "newzealand:nz_pci:data"

    def __init__(self):
        pass

    # =========================================================================
    # PMI
    # =========================================================================

    def get_pmi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """製造業PMIデータを取得"""
        next_release = self._get_next_release(PMI_FMP_PATTERN)

        if not force_refresh:
            cached = redis_client.get(self.PMI_CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(PMI_FMP_PATTERN, last_updated_str):
                    return {
                        "data": cached.get("data", []),
                        "latest": cached.get("latest"),
                        "metadata": cached.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        data = self._load_pmi_data()
        return self._build_response(
            data=data,
            cache_key=self.PMI_CACHE_KEY,
            cache_file=PMI_CACHE_FILE,
            indicator="BusinessNZ Manufacturing PMI",
            description="製造業PMI（季節調整済み）",
            next_release=next_release,
        )

    def _load_pmi_data(self) -> List[Dict[str, Any]]:
        """PMIデータをExcel + DB + FMPからマージして取得"""
        result = []
        try:
            excel_data = self._fetch_excel_pmi()
            result.extend(excel_data)

            db_data = self._load_from_db(PMI_FMP_PATTERN)
            result.extend(db_data)

            fmp_data = self._fetch_from_fmp(PMI_FMP_PATTERN)
            result.extend(fmp_data)

            merged = {}
            for item in result:
                merged[item["date"]] = item
            result = sorted(merged.values(), key=lambda x: x["date"])
            print(f"[NzPmi] PMI: {len(result)} records (merged)")
        except Exception as e:
            print(f"[NzPmi] Error loading PMI data: {e}")
            import traceback
            traceback.print_exc()
        return result

    def _fetch_excel_pmi(self) -> List[Dict[str, Any]]:
        """PMI ExcelファイルからSA値を取得"""
        return self._fetch_excel_single(
            url=PMI_URL,
            sheet_name="Seasonally Adjusted",
            header_row=1,
            data_start_row=2,
            date_col=0,
            value_col=1,
            label="PMI",
        )

    # =========================================================================
    # PSI
    # =========================================================================

    def get_psi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """サービス業PSIデータを取得"""
        next_release = self._get_next_release(PSI_FMP_PATTERN)

        if not force_refresh:
            cached = redis_client.get(self.PSI_CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(PSI_FMP_PATTERN, last_updated_str):
                    return {
                        "data": cached.get("data", []),
                        "latest": cached.get("latest"),
                        "metadata": cached.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        data = self._load_psi_data()
        return self._build_response(
            data=data,
            cache_key=self.PSI_CACHE_KEY,
            cache_file=PSI_CACHE_FILE,
            indicator="BusinessNZ Performance of Services Index (PSI)",
            description="サービス業PSI（季節調整済み）",
            next_release=next_release,
        )

    def _load_psi_data(self) -> List[Dict[str, Any]]:
        """PSIデータをExcel + DB + FMPからマージして取得"""
        result = []
        try:
            excel_data = self._fetch_excel_psi()
            result.extend(excel_data)

            db_data = self._load_from_db(PSI_FMP_PATTERN)
            result.extend(db_data)

            fmp_data = self._fetch_from_fmp(PSI_FMP_PATTERN)
            result.extend(fmp_data)

            merged = {}
            for item in result:
                merged[item["date"]] = item
            result = sorted(merged.values(), key=lambda x: x["date"])
            print(f"[NzPmi] PSI: {len(result)} records (merged)")
        except Exception as e:
            print(f"[NzPmi] Error loading PSI data: {e}")
            import traceback
            traceback.print_exc()
        return result

    def _fetch_excel_psi(self) -> List[Dict[str, Any]]:
        """PSI ExcelファイルからSA値を取得"""
        return self._fetch_excel_single(
            url=PSI_URL,
            sheet_name="PSI Seasonally Adjusted",
            header_row=1,
            data_start_row=2,
            date_col=0,
            value_col=1,
            label="PSI",
        )

    # =========================================================================
    # PCI
    # =========================================================================

    def get_pci_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """総合PCIデータを取得"""
        next_release = self._get_next_release(PCI_FMP_PATTERN)

        if not force_refresh:
            cached = redis_client.get(self.PCI_CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(PCI_FMP_PATTERN, last_updated_str):
                    return {
                        "data": cached.get("data", []),
                        "latest": cached.get("latest"),
                        "metadata": cached.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        data = self._load_pci_data()
        return self._build_response(
            data=data,
            cache_key=self.PCI_CACHE_KEY,
            cache_file=PCI_CACHE_FILE,
            indicator="BusinessNZ/BNZ Performance of Composite Index (PCI)",
            description="総合PCI（GDP加重・季節調整済み）",
            next_release=next_release,
        )

    def _load_pci_data(self) -> List[Dict[str, Any]]:
        """PCIデータをExcel + DB + FMPからマージして取得"""
        result = []
        try:
            excel_data = self._fetch_excel_pci()
            result.extend(excel_data)

            db_data = self._load_from_db(PCI_FMP_PATTERN)
            result.extend(db_data)

            fmp_data = self._fetch_from_fmp(PCI_FMP_PATTERN)
            result.extend(fmp_data)

            merged = {}
            for item in result:
                merged[item["date"]] = item
            result = sorted(merged.values(), key=lambda x: x["date"])
            print(f"[NzPmi] PCI: {len(result)} records (merged)")
        except Exception as e:
            print(f"[NzPmi] Error loading PCI data: {e}")
            import traceback
            traceback.print_exc()
        return result

    def _fetch_excel_pci(self) -> List[Dict[str, Any]]:
        """PCI ExcelファイルからSA値（GDP Weighted Combined Index）を取得"""
        return self._fetch_excel_single(
            url=PCI_URL,
            sheet_name="Combined Seasonally Adjusted",
            header_row=1,
            data_start_row=2,
            date_col=0,
            value_col=1,
            label="PCI",
        )

    # =========================================================================
    # 共通Excel取得
    # =========================================================================

    def _fetch_excel_single(
        self,
        url: str,
        sheet_name: str,
        header_row: int,
        data_start_row: int,
        date_col: int,
        value_col: int,
        label: str,
    ) -> List[Dict[str, Any]]:
        """BusinessNZ Excelファイルから時系列データを取得

        構造:
        - header_row: ヘッダー行（0-indexed）
        - data_start_row: データ開始行（0-indexed）
        - date_col: 日付列インデックス（0-indexed）
        - value_col: 値列インデックス（0-indexed）
        """
        result = []
        try:
            resp = requests.get(url, timeout=60, headers=EXCEL_HTTP_HEADERS)
            resp.raise_for_status()

            content = io.BytesIO(resp.content)
            df = pd.read_excel(content, sheet_name=sheet_name, header=None, engine="xlrd")

            for row_idx in range(data_start_row, df.shape[0]):
                date_val = df.iloc[row_idx, date_col]
                value_val = df.iloc[row_idx, value_col]

                if pd.isna(date_val) or pd.isna(value_val):
                    continue

                # 日付変換
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime("%Y-%m-%d")
                elif hasattr(date_val, "date"):
                    date_str = date_val.date().strftime("%Y-%m-%d")
                else:
                    try:
                        dt = pd.to_datetime(date_val)
                        date_str = dt.strftime("%Y-%m-%d")
                    except Exception:
                        continue

                # 値変換
                try:
                    value = round(float(value_val), 2)
                except (ValueError, TypeError):
                    continue

                result.append({"date": date_str, "value": value})

            print(f"[NzPmi] {label}: {len(result)} records from Excel")

        except Exception as e:
            print(f"[NzPmi] Error fetching {label} Excel: {e}")
            import traceback
            traceback.print_exc()

        return result

    # =========================================================================
    # DB取得（共通）
    # =========================================================================

    def _load_from_db(self, fmp_pattern: str) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        result = []
        try:
            with SessionLocal() as session:
                query = text("""
                    SELECT
                        datetime_utc,
                        event,
                        actual
                    FROM economic_calendar_events
                    WHERE country = :country
                      AND LOWER(event) LIKE LOWER(:pattern)
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query, {
                    "country": FMP_COUNTRY,
                    "pattern": f"%{fmp_pattern}%",
                }).fetchall()

                for row in rows:
                    dt_utc, event, actual = row
                    if not dt_utc:
                        continue

                    # 発表月の前月を対象月として使用（月次・当月翌月初公表パターン）
                    dt_auckland = dt_utc.replace(tzinfo=UTC).astimezone(AUCKLAND) if dt_utc.tzinfo is None else dt_utc.astimezone(AUCKLAND)
                    # 前月の1日
                    if dt_auckland.month == 1:
                        target_year = dt_auckland.year - 1
                        target_month = 12
                    else:
                        target_year = dt_auckland.year
                        target_month = dt_auckland.month - 1

                    date_str = f"{target_year}-{target_month:02d}-01"
                    result.append({
                        "date": date_str,
                        "value": round(float(actual), 2) if actual else None,
                    })

            print(f"[NzPmi] '{fmp_pattern}': {len(result)} records from DB")
        except Exception as e:
            print(f"[NzPmi] Error loading from DB ('{fmp_pattern}'): {e}")
        return result

    # =========================================================================
    # FMP取得（共通）
    # =========================================================================

    def _fetch_from_fmp(self, fmp_pattern: str) -> List[Dict[str, Any]]:
        """FMPから最新データを取得（前回値修正を含む）"""
        result = []
        try:
            today = date.today()
            from_date = today - timedelta(days=90)
            to_date = today + timedelta(days=60)

            events = fmp_service.fetch_calendar(from_date, to_date, country=FMP_COUNTRY)

            for event in events:
                if event.get("country") != FMP_COUNTRY:
                    continue
                event_name = event.get("event", "")
                if fmp_pattern.lower() not in event_name.lower():
                    continue

                actual = event.get("actual")
                if actual is None:
                    continue

                dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
                if not dt_utc:
                    continue

                # 発表月の前月を対象月とする
                dt_auckland = dt_utc.astimezone(AUCKLAND)
                if dt_auckland.month == 1:
                    target_year = dt_auckland.year - 1
                    target_month = 12
                else:
                    target_year = dt_auckland.year
                    target_month = dt_auckland.month - 1

                date_str = f"{target_year}-{target_month:02d}-01"
                result.append({"date": date_str, "value": round(float(actual), 2)})

                # 前回値の修正を反映
                previous = event.get("previous")
                if previous is not None:
                    prev_date = self._get_previous_month_date(date_str)
                    result.append({"date": prev_date, "value": round(float(previous), 2)})

                # DBにも保存
                self._save_to_db(event)

            print(f"[NzPmi] '{fmp_pattern}': {len(result)} records from FMP")
        except Exception as e:
            print(f"[NzPmi] Error fetching from FMP ('{fmp_pattern}'): {e}")
        return result

    def _get_previous_month_date(self, date_str: str) -> str:
        """前月の日付を取得"""
        try:
            parts = date_str.split("-")
            year, month = int(parts[0]), int(parts[1])
            if month == 1:
                return f"{year - 1}-12-01"
            return f"{year}-{month - 1:02d}-01"
        except Exception:
            return date_str

    def _save_to_db(self, event: dict) -> None:
        """FMPイベントをDBに保存"""
        try:
            processed = fmp_service.process_event(event)
            with SessionLocal() as session:
                query = text("""
                    INSERT INTO economic_calendar_events (
                        provider, event_key, country, currency, event, event_period,
                        datetime_raw, datetime_utc, has_time, impact,
                        previous, estimate, actual, change, change_pct, unit, raw_json
                    ) VALUES (
                        :provider, :event_key, :country, :currency, :event, :event_period,
                        :datetime_raw, :datetime_utc, :has_time, :impact,
                        :previous, :estimate, :actual, :change, :change_pct, :unit, :raw_json
                    )
                    ON CONFLICT (provider, event_key) DO UPDATE SET
                        previous = EXCLUDED.previous,
                        estimate = EXCLUDED.estimate,
                        actual = EXCLUDED.actual,
                        change = EXCLUDED.change,
                        change_pct = EXCLUDED.change_pct,
                        updated_at = NOW()
                """)
                session.execute(query, {
                    "provider": processed["provider"],
                    "event_key": processed["event_key"],
                    "country": processed["country"],
                    "currency": processed["currency"],
                    "event": processed["event"],
                    "event_period": processed["event_period"],
                    "datetime_raw": processed["datetime_raw"],
                    "datetime_utc": processed["datetime_utc"],
                    "has_time": processed["has_time"],
                    "impact": processed["impact"],
                    "previous": processed["previous"],
                    "estimate": processed["estimate"],
                    "actual": processed["actual"],
                    "change": processed["change"],
                    "change_pct": processed["change_pct"],
                    "unit": processed["unit"],
                    "raw_json": json.dumps(processed["raw_json"]),
                })
                session.commit()
        except Exception as e:
            print(f"[NzPmi] Error saving to DB: {e}")

    # =========================================================================
    # キャッシュ・ユーティリティ
    # =========================================================================

    def _build_response(
        self,
        data: List[Dict[str, Any]],
        cache_key: str,
        cache_file: Path,
        indicator: str,
        description: str,
        next_release: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """レスポンスを構築してキャッシュに保存"""
        latest = data[-1] if data else None
        from services.usa.fmp_next_release_utils import guarded_last_updated
        now_str = datetime.now(JST).isoformat()
        last_updated = guarded_last_updated(
            cache_key, latest.get("date") if latest else None, now_str
        )
        metadata = {
            "source": "BusinessNZ",
            "indicator": indicator,
            "description": description,
            "unit": "index",
            "frequency": "monthly",
        }
        cache_payload = {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "last_updated": last_updated,
        }
        redis_client.set(cache_key, cache_payload, expire=0)
        self._save_file_cache(cache_file, cache_payload)

        return {
            "data": data,
            "latest": latest,
            "metadata": metadata,
            "next_release": next_release,
            "cached": False,
            "source": "excel+db+fmp",
            "last_updated": last_updated,
        }

    def _get_next_release(self, fmp_pattern: str) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(fmp_pattern, country=FMP_COUNTRY)
        except Exception as e:
            print(f"[NzPmi] Error getting next release ('{fmp_pattern}'): {e}")
            return None

    def _should_refresh(self, fmp_pattern: str, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(fmp_pattern, last_updated_str, country=FMP_COUNTRY)
        except Exception:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                return (datetime.now(JST) - last_updated).total_seconds() > 86400
            except Exception:
                return True

    def _save_file_cache(self, cache_file: Path, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[NzPmi] Failed to save file cache ({cache_file}): {e}")

    # =========================================================================
    # キャッシュ管理
    # =========================================================================

    def invalidate_pmi_cache(self) -> bool:
        return redis_client.delete(self.PMI_CACHE_KEY)

    def invalidate_psi_cache(self) -> bool:
        return redis_client.delete(self.PSI_CACHE_KEY)

    def invalidate_pci_cache(self) -> bool:
        return redis_client.delete(self.PCI_CACHE_KEY)

    def get_pmi_cache_status(self) -> Dict[str, Any]:
        return self._get_cache_status(self.PMI_CACHE_KEY, PMI_CACHE_FILE, "BusinessNZ Manufacturing PMI", PMI_FMP_PATTERN)

    def get_psi_cache_status(self) -> Dict[str, Any]:
        return self._get_cache_status(self.PSI_CACHE_KEY, PSI_CACHE_FILE, "BusinessNZ PSI", PSI_FMP_PATTERN)

    def get_pci_cache_status(self) -> Dict[str, Any]:
        return self._get_cache_status(self.PCI_CACHE_KEY, PCI_CACHE_FILE, "BusinessNZ PCI", PCI_FMP_PATTERN)

    def _get_cache_status(self, cache_key: str, cache_file: Path, indicator: str, fmp_pattern: str) -> Dict[str, Any]:
        data_exists = redis_client.exists(cache_key)
        cached_data = redis_client.get(cache_key) if data_exists else None
        return {
            "indicator": indicator,
            "source": "BusinessNZ / Excel / FMP",
            "cache_key": cache_key,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "next_release": self._get_next_release(fmp_pattern),
            "file_cache_exists": cache_file.exists(),
        }


# シングルトンインスタンス
nz_pmi_service = NzPmiService()
