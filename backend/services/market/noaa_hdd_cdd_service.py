"""
NOAA HDD/CDD & 気温見通しサービス

データソース:
  - NOAA CPC FTP: 日次 Population-Weighted HDD/CDD (2016〜)
  - NOAA CPC FTP: 7日先予測 HDD/CDD
  - NOAA CPC: 6-10日 / 8-14日 気温見通し (fxus06)

更新スケジュール: 日次（JST 5:00）
更新: 6時間TTL (Redis + ファイル)
"""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "noaa_hdd_cdd_cache.json"

REDIS_KEY = "market:noaa_hdd_cdd:data"

# データソースURL
DAILY_BASE_URL = (
    "https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/"
    "daily_data/{year}/Population.{series}.txt"
)
FORECAST_BASE_URL = (
    "https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/"
    "daily_forecasts_7day/latest/Population.{series}.txt"
)
OUTLOOK_URL = (
    "https://www.cpc.ncep.noaa.gov/products/predictions/610day/fxus06.html"
)
WEEK34_URL = (
    "https://www.cpc.ncep.noaa.gov/products/predictions/WK34/texts/week34fcst.txt"
)

START_YEAR = 2016


class NoaaHddCddService:
    """NOAA CPC HDD/CDD & 気温見通しサービス"""

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
            logger.error(f"[NoaaHddCdd] Build error: {e}")
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
            "outlook": None,
            "metadata": {"source": "NOAA CPC"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """全データを取得・構築"""
        logger.info("[NoaaHddCdd] Building data from NOAA CPC...")

        # 1. 日次観測データ（10年分）
        daily_data = self._fetch_all_daily_data()
        if not daily_data:
            logger.error("[NoaaHddCdd] No daily data fetched")
            return None

        # 2. 7日先予測
        forecast_data = self._fetch_forecast_7day()

        # 3. 既存データの最終日以降の予測のみ追加
        if forecast_data:
            last_observed_date = daily_data[-1]["date"]
            for item in forecast_data:
                if item["date"] > last_observed_date:
                    daily_data.append(item)

        # 4. 気温見通し（6-10日/8-14日）
        outlook = self._fetch_outlook()

        # 5. Week 3-4 見通し（テキスト要約）
        week34 = self._fetch_week34()
        if outlook and week34:
            outlook["3_4"] = week34
        elif week34:
            outlook = {"3_4": week34}

        # latest = 予測を除いた最新の観測値
        observed = [d for d in daily_data if not d.get("forecast")]
        latest = observed[-1].copy() if observed else None

        now_str = datetime.now(JST).isoformat()

        forecast_end = daily_data[-1]["date"] if daily_data else None

        logger.info(
            f"[NoaaHddCdd] {len(daily_data)} data points "
            f"({daily_data[0]['date']} ~ {daily_data[-1]['date']}), "
            f"latest HDD={latest.get('hdd') if latest else '?'}, "
            f"CDD={latest.get('cdd') if latest else '?'}"
        )

        return {
            "data": daily_data,
            "latest": latest,
            "outlook": outlook,
            "metadata": {
                "source": "NOAA CPC",
                "frequency": "daily",
                "unit": "degree days",
                "series": "Population-Weighted CONUS HDD/CDD",
                "data_count": len(daily_data),
                "start_date": daily_data[0]["date"],
                "end_date": daily_data[-1]["date"],
                "forecast_end_date": forecast_end,
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    # ── 日次観測データ取得 ──

    def _fetch_all_daily_data(self) -> Optional[List[Dict[str, Any]]]:
        """10年分の日次HDD/CDDを並列取得してマージ"""
        current_year = datetime.now(JST).year
        years = list(range(START_YEAR, current_year + 1))

        # {date_str: {"hdd": val, "cdd": val}}
        merged: Dict[str, Dict[str, int]] = {}

        def fetch_year_series(year: int, series: str) -> Tuple[str, Dict[str, int]]:
            url = DAILY_BASE_URL.format(year=year, series=series)
            try:
                resp = requests.get(url, timeout=30,
                                    headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    logger.warning(
                        f"[NoaaHddCdd] {series}/{year}: HTTP {resp.status_code}")
                    return (series, {})
                return (series, self._parse_daily_file(resp.text))
            except Exception as e:
                logger.warning(f"[NoaaHddCdd] {series}/{year}: {e}")
                return (series, {})

        # 並列取得: 年 × 系列
        tasks = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for year in years:
                for series in ("Heating", "Cooling"):
                    tasks.append(
                        executor.submit(fetch_year_series, year, series))

            for future in as_completed(tasks):
                series_name, date_vals = future.result()
                field = "hdd" if series_name == "Heating" else "cdd"
                for date_str, val in date_vals.items():
                    if date_str not in merged:
                        merged[date_str] = {"hdd": 0, "cdd": 0}
                    merged[date_str][field] = val

        if not merged:
            return None

        # ソートしてリスト化
        result = []
        for date_str in sorted(merged.keys()):
            vals = merged[date_str]
            result.append({
                "date": date_str,
                "hdd": vals.get("hdd", 0),
                "cdd": vals.get("cdd", 0),
            })

        logger.info(f"[NoaaHddCdd] Daily data: {len(result)} points "
                     f"({result[0]['date']} ~ {result[-1]['date']})")
        return result

    def _parse_daily_file(self, text: str) -> Dict[str, int]:
        """パイプ区切りファイルをパースしてCONUS行を抽出

        フォーマット:
        Line 1: Product: Daily Heating Degree Days ...
        Line 2: Regions: CPC::Regions::CensusDivisions
        Line 3: Weights: Population
        Line 4: Region|YYYYMMDD|YYYYMMDD|...
        Lines 5-14: 1|val|val|... through CONUS|val|val|...
        """
        lines = text.strip().split("\n")
        if len(lines) < 5:
            return {}

        # 日付ヘッダー行（4行目）
        header_line = lines[3]
        header_parts = header_line.split("|")
        if len(header_parts) < 2:
            return {}

        # 日付カラム: YYYYMMDD → YYYY-MM-DD
        date_columns = []
        for part in header_parts[1:]:
            raw = part.strip()
            if len(raw) == 8 and raw.isdigit():
                date_columns.append(
                    f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}")
            else:
                date_columns.append(None)

        # CONUS行を検索
        for line in lines[4:]:
            parts = line.split("|")
            if not parts:
                continue
            region = parts[0].strip()
            if region == "CONUS":
                result: Dict[str, int] = {}
                for i, date_str in enumerate(date_columns):
                    if date_str is None:
                        continue
                    col_idx = i + 1
                    if col_idx >= len(parts):
                        break
                    raw_val = parts[col_idx].strip()
                    if not raw_val:
                        continue
                    try:
                        result[date_str] = int(raw_val)
                    except (ValueError, TypeError):
                        continue
                return result

        return {}

    # ── 7日先予測取得 ──

    def _fetch_forecast_7day(self) -> Optional[List[Dict[str, Any]]]:
        """7日先予測のHDD/CDDを取得"""
        hdd_vals: Dict[str, int] = {}
        cdd_vals: Dict[str, int] = {}

        for series, target in [("Heating", hdd_vals), ("Cooling", cdd_vals)]:
            url = FORECAST_BASE_URL.format(series=series)
            try:
                resp = requests.get(url, timeout=30,
                                    headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    logger.warning(
                        f"[NoaaHddCdd] Forecast {series}: "
                        f"HTTP {resp.status_code}")
                    continue
                parsed = self._parse_daily_file(resp.text)
                target.update(parsed)
            except Exception as e:
                logger.warning(f"[NoaaHddCdd] Forecast {series}: {e}")

        if not hdd_vals and not cdd_vals:
            return None

        # マージ
        all_dates = sorted(set(hdd_vals.keys()) | set(cdd_vals.keys()))
        result = []
        for date_str in all_dates:
            result.append({
                "date": date_str,
                "hdd": hdd_vals.get(date_str, 0),
                "cdd": cdd_vals.get(date_str, 0),
                "forecast": True,
            })

        logger.info(f"[NoaaHddCdd] Forecast: {len(result)} days")
        return result

    # ── 気温見通し取得 ──

    def _fetch_outlook(self) -> Optional[Dict[str, Any]]:
        """6-10日/8-14日気温見通しを取得"""
        try:
            resp = requests.get(OUTLOOK_URL, timeout=30,
                                headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                logger.warning(
                    f"[NoaaHddCdd] Outlook: HTTP {resp.status_code}")
                return None
            return self._parse_outlook(resp.text)
        except Exception as e:
            logger.warning(f"[NoaaHddCdd] Outlook fetch error: {e}")
            return None

    def _parse_outlook(self, html: str) -> Optional[Dict[str, Any]]:
        """fxus06.htmlから6-10日/8-14日見通しテーブルをパース"""
        # HTMLタグ除去
        text = re.sub(r"<[^>]+>", "", html)
        text = text.replace("&amp;", "&").replace("&lt;", "<") \
                    .replace("&gt;", ">").replace("&nbsp;", " ")

        result: Dict[str, Any] = {}

        for period_key, search_str in [
            ("6_10", "6-10 DAY OUTLOOK TABLE"),
            ("8_14", "8-14 DAY OUTLOOK TABLE"),
        ]:
            idx = text.find(search_str)
            if idx == -1:
                continue

            # このセクションのテキストを切り出し
            section = text[idx:idx + 3000]
            lines = section.split("\n")

            # 日付範囲を抽出
            date_range = ""
            for line in lines[:5]:
                m = re.search(
                    r"Outlook\s+for\s+(.+?\d{4})", line, re.IGNORECASE)
                if m:
                    date_range = m.group(1).strip()
                    break

            # 州データをパース
            states: List[Dict[str, str]] = []
            parsing = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if parsing:
                        # 空行 = テーブル終了
                        break
                    continue

                # ヘッダー行をスキップ
                if "STATE" in stripped and "TEMP" in stripped:
                    parsing = True
                    continue

                if not parsing:
                    continue

                # 固定幅3州/行パース
                # 各エントリは約23文字幅
                parsed = self._parse_outlook_line(stripped)
                states.extend(parsed)

            if states:
                result[period_key] = {
                    "date_range": date_range,
                    "states": states,
                }

        return result if result else None

    def _parse_outlook_line(self, line: str) -> List[Dict[str, str]]:
        """見通しテーブルの1行をパースして州リストを返す

        フォーマット（固定幅22文字/エントリ × 3エントリ/行）:
        WASHINGTON  A    A     OREGON      A    B     NRN CALIF   A    B
        AK SO COAST B    B     AK PNHDL    B    A
        """
        results: List[Dict[str, str]] = []

        # 固定幅22文字で分割（最後のエントリは短い場合あり）
        raw = line.rstrip()
        if not raw.strip():
            return results

        col_width = 22
        chunks = []
        for start in range(0, len(raw), col_width):
            chunk = raw[start:start + col_width].strip()
            if chunk:
                chunks.append(chunk)

        for chunk in chunks:
            # "STATE_NAME  A    B" パターンでマッチ
            m = re.match(
                r"^(.+?)\s+(A|B|N)\s+(A|B|N)\s*$", chunk)
            if m:
                state = m.group(1).strip()
                temp = m.group(2)
                precip = m.group(3)
                if state:
                    results.append({
                        "state": state,
                        "temp": temp,
                        "precip": precip,
                    })

        return results

    # ── Week 3-4 見通し取得 ──

    def _fetch_week34(self) -> Optional[Dict[str, Any]]:
        """Week 3-4 気温・降水見通しテキストを取得・パース"""
        try:
            resp = requests.get(WEEK34_URL, timeout=30,
                                headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                logger.warning(
                    f"[NoaaHddCdd] Week 3-4: HTTP {resp.status_code}")
                return None
            return self._parse_week34(resp.text)
        except Exception as e:
            logger.warning(f"[NoaaHddCdd] Week 3-4 fetch error: {e}")
            return None

    def _parse_week34(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Week 3-4 テキストからサマリー情報を抽出

        Week 3-4 はテーブル形式ではなく narrative のみ。
        有効期間・気温見通し・降水見通し・発行者情報を抽出する。
        """
        # HTMLタグ除去
        text = re.sub(r"<[^>]*>", "", raw_text)
        text = text.replace("&amp;", "&").replace("&#39;", "'") \
                    .replace("&nbsp;", " ")

        # 有効期間
        date_range = ""
        m = re.search(
            r"Valid\s+(.+?\d{4})\s*[-–]\s*(.+?\d{4})",
            text, re.IGNORECASE)
        if m:
            date_range = f"{m.group(1).strip()} - {m.group(2).strip()}"

        # 発行日
        issued = ""
        m_issued = re.search(
            r"Forecaster:\s*(.+?)(?:\n|$)", text)
        if m_issued:
            issued = m_issued.group(1).strip()

        # 気温見通し段落を抽出
        temp_summary = ""
        temp_match = re.search(
            r"(?:Week 3-4 )?Temperature Outlook\s+(.+?)(?=Week 3-4 Precipitation|Precipitation Outlook|$)",
            text, re.DOTALL | re.IGNORECASE)
        if temp_match:
            temp_summary = re.sub(r"\s+", " ", temp_match.group(1)).strip()

        # 降水見通し段落を抽出
        precip_summary = ""
        precip_match = re.search(
            r"(?:Week 3-4 )?Precipitation Outlook\s+(.+?)(?=SSTs around|Forecaster:|$)",
            text, re.DOTALL | re.IGNORECASE)
        if precip_match:
            precip_summary = re.sub(r"\s+", " ", precip_match.group(1)).strip()

        if not date_range and not temp_summary:
            return None

        result: Dict[str, Any] = {
            "date_range": date_range,
            "forecaster": issued,
            "temp_summary": temp_summary,
            "precip_summary": precip_summary,
        }

        logger.info(
            f"[NoaaHddCdd] Week 3-4 outlook: {date_range}, "
            f"forecaster={issued}")

        return result

    # ── キャッシュ ──

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NoaaHddCdd] Redis save error: {e}")
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[NoaaHddCdd] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NoaaHddCdd] Redis load error: {e}")
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
            logger.error(f"[NoaaHddCdd] File load error: {e}")
        return None


noaa_hdd_cdd_service = NoaaHddCddService()
