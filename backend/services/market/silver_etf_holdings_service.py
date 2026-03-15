"""
銀ETF残高保有量 (iShares Silver Trust - SLV) サービス

データソース:
  - BlackRock: iShares Silver Trust Fund Excel (XML Spreadsheet形式)
  - URL: https://www.blackrock.com/jp/individual/ja/products/239855/ishares-silver-trust-fund/1535604546378.ajax?fileType=xls&fileName=iShares-Silver-Trust_fund&dataType=fund
  - Sheet: 基準価額履歴
  - 計算: 発行済口数 × 0.97oz / 32150.7 = 銀保有量（トン）

更新スケジュール: 日次（JST 8:30）
更新: 6時間TTL (Redis + ファイル)

注意: BlackRockが返すxlsファイルはMicrosoft XML Spreadsheet 2003形式
      (openpyxl/xlrdでは読めないため、xml.etree.ElementTreeで直接パース)
"""
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "silver_etf_holdings_cache.json"

REDIS_KEY = "market:silver_etf_holdings:data"

EXCEL_URL = (
    "https://www.blackrock.com/jp/individual/ja/products/239855/"
    "ishares-silver-trust-fund/1535604546378.ajax"
    "?fileType=xls&fileName=iShares-Silver-Trust_fund&dataType=fund"
)

# iShares Silver Trust: 1口あたり銀保有量 (oz)
SILVER_PER_SHARE_OZ = 0.97
# 1トン = 32,150.7 トロイオンス
OZ_PER_TON = 32150.7

# XML Spreadsheet 2003 namespace
NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}


class SilverEtfHoldingsService:
    """銀ETF残高保有量 (iShares Silver Trust) サービス"""

    def _should_refresh(self) -> bool:
        try:
            cached = redis_client.get(REDIS_KEY)
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() >= 6 * 3600
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """銀ETF残高データを取得"""
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[SilverEtf] Build error: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "iShares Silver Trust (BlackRock)"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """BlackRockからXML Spreadsheetをダウンロードしてパース"""
        logger.info("[SilverEtf] Building data from BlackRock Excel...")

        try:
            resp = requests.get(EXCEL_URL, timeout=60, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code != 200 or len(resp.content) < 1000:
                logger.error(
                    f"[SilverEtf] Download failed: status={resp.status_code}, "
                    f"size={len(resp.content)}"
                )
                return None
        except Exception as e:
            logger.error(f"[SilverEtf] Download error: {e}")
            return None

        logger.info(f"[SilverEtf] Downloaded {len(resp.content)} bytes")

        return self._parse_xml_spreadsheet(resp.content)

    def _parse_xml_spreadsheet(self, xml_bytes: bytes) -> Optional[Dict[str, Any]]:
        """Microsoft XML Spreadsheet 2003形式をパース

        構造:
          <ss:Workbook>
            <ss:Worksheet ss:Name="基準価額履歴">
              <ss:Table>
                <ss:Row>  ← ヘッダー行: 日付, 基準価額, 分配金単価, 発行済口数, 純資産総額
                <ss:Row>  ← データ行
                  <ss:Cell><ss:Data ss:Type="String">2026年3月10日</ss:Data></ss:Cell>
                  ...
                  <ss:Cell><ss:Data ss:Type="Number">555600000</ss:Data></ss:Cell>  ← 発行済口数
                  ...
        """
        try:
            # BOM除去
            content = xml_bytes.decode("utf-8-sig")
            root = ET.fromstring(content)
        except Exception as e:
            logger.error(f"[SilverEtf] XML parse error: {e}")
            return None

        # 基準価額履歴シートを探す
        target_sheet = None
        for ws in root.findall("ss:Worksheet", NS):
            name = ws.get(f"{{{NS['ss']}}}Name", "")
            if "基準価額" in name or "履歴" in name:
                target_sheet = ws
                break

        if target_sheet is None:
            # フォールバック: 2番目のシート（1番目はDisclaimers）
            sheets = root.findall("ss:Worksheet", NS)
            if len(sheets) >= 2:
                target_sheet = sheets[1]
            elif sheets:
                target_sheet = sheets[0]
            else:
                logger.error("[SilverEtf] No worksheets found")
                return None

        table = target_sheet.find("ss:Table", NS)
        if table is None:
            logger.error("[SilverEtf] No Table element in worksheet")
            return None

        rows = table.findall("ss:Row", NS)
        if len(rows) < 2:
            logger.error("[SilverEtf] Not enough rows in table")
            return None

        # ヘッダー行を解析して列インデックスを特定
        header_row = rows[0]
        header_cells = header_row.findall("ss:Cell", NS)
        headers = []
        for cell in header_cells:
            data_el = cell.find("ss:Data", NS)
            headers.append(data_el.text if data_el is not None else "")

        logger.info(f"[SilverEtf] Headers: {headers}")

        # 列インデックスを特定
        date_idx = None
        shares_idx = None
        for i, h in enumerate(headers):
            if h and "日付" in h:
                date_idx = i
            if h and "発行済口数" in h:
                shares_idx = i

        if date_idx is None:
            date_idx = 0
            logger.warning("[SilverEtf] Date column not found, using index 0")
        if shares_idx is None:
            logger.error(f"[SilverEtf] Shares column not found in headers: {headers}")
            return None

        # データ行をパース
        result_data: List[Dict[str, Any]] = []

        for row in rows[1:]:
            cells = row.findall("ss:Cell", NS)
            if len(cells) <= max(date_idx, shares_idx):
                continue

            # セル値を取得
            cell_values = []
            for cell in cells:
                data_el = cell.find("ss:Data", NS)
                cell_values.append(data_el.text if data_el is not None else None)

            if len(cell_values) <= max(date_idx, shares_idx):
                continue

            # 日付パース
            raw_date = cell_values[date_idx]
            date_str = self._parse_date(raw_date)
            if not date_str:
                continue

            # 発行済口数パース
            raw_shares = cell_values[shares_idx]
            shares = self._parse_number(raw_shares)
            if shares is None or shares <= 0:
                continue

            # 銀保有量（トン）= 発行済口数 × 0.97oz / 32150.7
            silver_tons = round((shares * SILVER_PER_SHARE_OZ) / OZ_PER_TON, 2)

            result_data.append({
                "date": date_str,
                "silver_tons": silver_tons,
                "shares_outstanding": int(shares),
            })

        if not result_data:
            logger.error("[SilverEtf] No data parsed from XML")
            return None

        # 日付昇順ソート
        result_data.sort(key=lambda x: x["date"])

        # 重複日付を除去（最新のものを残す）
        seen: Dict[str, Dict[str, Any]] = {}
        for item in result_data:
            seen[item["date"]] = item
        result_data = sorted(seen.values(), key=lambda x: x["date"])

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        logger.info(
            f"[SilverEtf] Parsed {len(result_data)} data points "
            f"({result_data[0]['date']} ~ {result_data[-1]['date']}), "
            f"latest silver_tons={latest.get('silver_tons')}"
        )

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "iShares Silver Trust (BlackRock)",
                "indicator": "Silver ETF Balance Holdings (SLV)",
                "unit": "トン",
                "silver_per_share_oz": SILVER_PER_SHARE_OZ,
                "frequency": "daily",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    @staticmethod
    def _parse_date(raw) -> Optional[str]:
        """日付文字列をYYYY-MM-DD形式に変換"""
        if raw is None:
            return None
        if isinstance(raw, str):
            raw = raw.strip()
            # %Y年%m月%d日 形式
            m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
            if m:
                return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            # YYYY-MM-DD
            if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
                return raw[:10]
        return None

    @staticmethod
    def _parse_number(raw) -> Optional[float]:
        """数値文字列を解析"""
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str):
            try:
                return float(raw.replace(",", "").strip())
            except ValueError:
                return None
        return None

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[SilverEtf] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[SilverEtf] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[SilverEtf] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[SilverEtf] File load error: {e}")
        return None


# シングルトン
silver_etf_holdings_service = SilverEtfHoldingsService()
