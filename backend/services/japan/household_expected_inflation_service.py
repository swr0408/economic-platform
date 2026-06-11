"""
日銀 家計予想物価上昇率サービス（生活意識に関するアンケート調査）

日本銀行「生活意識に関するアンケート調査」のCSVから、家計レベルの物価予想・実感を取得。

指標（6系列, いずれも％）:
- 現在の物価実感（1年前比）  : 平均値 = S列, 中央値 = T列
- 1年後の物価予想            : 平均値 = AB列, 中央値 = AC列
- 5年後の物価予想（年平均）  : 平均値 = AW列, 中央値 = AX列

データソース:
- CSV: https://www.boj.or.jp/research/o_survey/survey04.csv （Shift-JIS）
- 調査概要: https://www.boj.or.jp/research/o_survey/index.htm

発表スケジュール:
- 四半期（年4回、おおむね1月・4月・7月・10月に公表）
- 次回発表日は「生活意識に関するアンケート調査」実施ページ（ishiki.htm）の
  「調査結果の公表は、YYYY年M月D日（曜）を予定」を優先的にスクレイピングし、
  取得できない場合は四半期スケジュールから推定する。

キャッシュ方式: 発表日時ベース判定 + 週次フォールバック
"""
import csv
import io
import json
import re
import requests
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "price"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "household_expected_inflation_cache.json"


class HouseholdExpectedInflationService:
    """日銀 家計予想物価上昇率サービス"""

    DATA_CACHE_KEY = "japan:household_expected_inflation:data"
    SCHEDULE_CACHE_KEY = "japan:household_expected_inflation:schedule"

    CSV_URL = "https://www.boj.or.jp/research/o_survey/survey04.csv"
    SURVEY_URL = "https://www.boj.or.jp/research/o_survey/ishiki.htm"

    HEADERS = {"User-Agent": "Mozilla/5.0 econalpha-release-checker/1.0"}

    # Excel列（0始まりインデックス）→ 出力系列名
    # S=18, T=19, AB=27, AC=28, AW=48, AX=49
    COLUMN_MAP = {
        "current_mean": 18,    # S  現在の物価実感（前年比）平均値
        "current_median": 19,  # T  現在の物価実感（前年比）中央値
        "exp1y_mean": 27,      # AB 1年後の物価予想 平均値
        "exp1y_median": 28,    # AC 1年後の物価予想 中央値
        "exp5y_mean": 48,      # AW 5年後の物価予想 平均値
        "exp5y_median": 49,    # AX 5年後の物価予想 中央値
    }

    # 公表月（1, 4, 7, 10月）。スクレイピング失敗時のフォールバック推定に使用
    RELEASE_MONTHS = [1, 4, 7, 10]

    _DATE_RE = re.compile(r"^(\d{4})年(\d{1,2})月")

    def __init__(self):
        pass

    def get_household_expected_inflation_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """家計予想物価上昇率データを取得（既存APIとの互換用エイリアス）"""
        return self.get_data(force_refresh=force_refresh)

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データを取得（キャッシュ優先）"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    cached_data["cached"] = True
                    cached_data["source"] = "redis"
                    cached_data["next_release"] = self._get_next_release()
                    return cached_data

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    file_cache["cached"] = True
                    file_cache["source"] = "file"
                    file_cache["next_release"] = self._get_next_release()
                    return file_cache

        # CSVからデータ取得
        data = self._fetch_from_csv()
        if data:
            latest = data[-1]
            next_release = self._get_next_release()
            now_str = datetime.now(JST).isoformat()

            cache_payload = {
                "data": data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": now_str,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "boj",
                "last_updated": now_str,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            file_cache["cached"] = True
            file_cache["source"] = "file (fallback)"
            file_cache["next_release"] = self._get_next_release()
            return file_cache

        return {
            "data": [],
            "latest": None,
            "next_release": self._get_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_csv(self) -> List[Dict[str, Any]]:
        """日銀CSVから6系列をパース"""
        try:
            print(f"Fetching Household Expected Inflation from: {self.CSV_URL}")
            resp = requests.get(self.CSV_URL, headers=self.HEADERS, timeout=60)
            resp.raise_for_status()

            # 日銀CSVはShift-JIS
            text = resp.content.decode("shift_jis", errors="replace")
            rows = list(csv.reader(io.StringIO(text)))

            result: List[Dict[str, Any]] = []
            for row in rows:
                if not row:
                    continue
                m = self._DATE_RE.match(row[0].strip())
                if not m:
                    # 脚注行・空行・ヘッダー行はスキップ
                    continue

                year, month = int(m.group(1)), int(m.group(2))
                entry: Dict[str, Any] = {"date": f"{year:04d}-{month:02d}-01"}

                has_value = False
                for name, idx in self.COLUMN_MAP.items():
                    val = self._parse_num(row[idx] if idx < len(row) else "")
                    entry[name] = val
                    if val is not None:
                        has_value = True

                if has_value:
                    result.append(entry)

            result.sort(key=lambda x: x["date"])
            print(f"Processed Household Expected Inflation: {len(result)} records")
            if result:
                print(f"Latest: {result[-1]}")
            return result

        except Exception as e:
            print(f"Error fetching Household Expected Inflation: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def _parse_num(raw: str) -> Optional[float]:
        v = (raw or "").strip()
        if v in ("", "-", "*", "…", "―", "ー"):
            return None
        try:
            return round(float(v), 2)
        except ValueError:
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきか判定（公表月の上旬 + 週次フォールバック）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            today = now.date()

            # 公表月（1,4,7,10月）の上中旬（1〜20日）はキャッシュが今日より古ければ更新
            if today.month in self.RELEASE_MONTHS and today.day <= 20:
                if last_updated.date() < today:
                    return True

            # 1週間以上経過していれば更新
            if (now - last_updated).days >= 7:
                return True

            return False
        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return True

    # -----------------------------------------------------------------
    # 次回発表日
    # -----------------------------------------------------------------
    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表予定日を取得。

        1) ishiki.htm をスクレイピングして確定日 / 概算を取得（Redis 1日キャッシュ）
        2) 取得できない場合は四半期スケジュールから推定
        """
        # スケジュールキャッシュ（1日）
        cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
        if cached:
            cached_at = cached.get("cached_at")
            try:
                if cached_at:
                    cdt = datetime.fromisoformat(cached_at)
                    if cdt.tzinfo is None:
                        cdt = cdt.replace(tzinfo=JST)
                    if (datetime.now(JST) - cdt).total_seconds() < 86400:
                        return cached.get("next_release")
            except Exception:
                pass

        next_release = self._scrape_next_release() or self._estimate_next_release()

        try:
            redis_client.set(
                self.SCHEDULE_CACHE_KEY,
                {"next_release": next_release, "cached_at": datetime.now(JST).isoformat()},
                expire=86400,
            )
        except Exception:
            pass

        return next_release

    def _scrape_next_release(self) -> Optional[Dict[str, Any]]:
        """ishiki.htm から次回公表日を抽出"""
        try:
            resp = requests.get(self.SURVEY_URL, headers=self.HEADERS, timeout=20)
            resp.raise_for_status()
            try:
                from bs4 import BeautifulSoup
                text = BeautifulSoup(resp.content, "html.parser").get_text("\n", strip=True)
            except Exception:
                text = resp.content.decode("utf-8", errors="replace")

            # 確定日: 「調査結果の公表は、YYYY年M月D日（曜）を予定」
            m = re.search(
                r"調査結果の公表は、(\d{4})年(\d{1,2})月(\d{1,2})日（[^）]+）を予定",
                text,
            )
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                try:
                    rd = date(y, mo, d)
                    return {
                        "date": rd.strftime("%Y-%m-%d"),
                        "datetime_jst": f"{rd.strftime('%Y-%m-%d')}T14:00:00+09:00",
                        "label": f"生活意識アンケート調査 - {rd.strftime('%Y/%m/%d')}（予定）",
                    }
                except ValueError:
                    pass

            # 概算: 「その結果をYYYY年M月（上旬/中旬/下旬等）に公表する予定」
            m = re.search(
                r"その結果を(\d{4})年(\d{1,2})月(上旬|中旬|下旬|上中旬|中下旬)に公表",
                text,
            )
            if m:
                y, mo, approx = int(m.group(1)), int(m.group(2)), m.group(3)
                day = {"上旬": 5, "上中旬": 10, "中旬": 15, "中下旬": 20, "下旬": 25}.get(approx, 10)
                rd = date(y, mo, day)
                return {
                    "date": rd.strftime("%Y-%m-%d"),
                    "datetime_jst": f"{rd.strftime('%Y-%m-%d')}T14:00:00+09:00",
                    "label": f"生活意識アンケート調査 - {y}年{mo}月{approx}（予定）",
                }

            return None
        except Exception as e:
            print(f"Error scraping survey release date: {e}")
            return None

    def _estimate_next_release(self) -> Optional[Dict[str, Any]]:
        """公表月（1,4,7,10月）の中旬を推定"""
        try:
            today = datetime.now(JST).date()
            for month in self.RELEASE_MONTHS:
                if month > today.month or (month == today.month and today.day < 20):
                    rd = date(today.year, month, 15)
                    return self._estimate_payload(rd)
            rd = date(today.year + 1, 1, 15)
            return self._estimate_payload(rd)
        except Exception as e:
            print(f"Error estimating next release: {e}")
            return None

    @staticmethod
    def _estimate_payload(rd: date) -> Dict[str, Any]:
        return {
            "date": rd.strftime("%Y-%m-%d"),
            "datetime_jst": f"{rd.strftime('%Y-%m-%d')}T14:00:00+09:00",
            "label": f"生活意識アンケート調査 - {rd.strftime('%Y/%m/%d')} 頃（推定）",
        }

    # -----------------------------------------------------------------
    # キャッシュ I/O
    # -----------------------------------------------------------------
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
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "Household Expected Inflation (BOJ Opinion Survey)",
            "source": "Bank of Japan",
            "url": self.CSV_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
household_expected_inflation_service = HouseholdExpectedInflationService()
