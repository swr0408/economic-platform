"""
10年物価連動国債BEI（ブレークイーブン・インフレ率）サービス
財務省PDFからBEIデータを取得

指標:
- 10年物価連動国債のブレークイーブン・インフレ率（%）
- 市場が予想する今後10年間の平均インフレ率を表す

データソース:
- PDF: https://www.mof.go.jp/jgbs/topics/bond/10year_inflation-indexed/bei.pdf
- 財務省が毎週土曜日に更新

発表スケジュール:
- 週次（毎週土曜日7:00 JST頃更新）

キャッシュ方式: 独自更新判定方式（次回土曜日ベース）
"""
import io
import json
import logging
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "bei_cache.json"

# PDF保存ディレクトリ
PDF_DIR = Path(__file__).parent.parent.parent / "data" / "pdf" / "japan"
PDF_DIR.mkdir(parents=True, exist_ok=True)
PDF_FILE = PDF_DIR / "bei.pdf"

# 財務省BEI PDFのURL
MOF_BEI_PDF_URL = "https://www.mof.go.jp/jgbs/topics/bond/10year_inflation-indexed/bei.pdf"


class BEIService:
    """10年物価連動国債BEIサービス"""

    DATA_CACHE_KEY = "japan:bei:data"

    def __init__(self):
        pass

    def get_bei_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """BEIデータを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # PDFからデータを取得
        pdf_data = self._fetch_data_from_pdf()

        if pdf_data:
            next_release = self._calculate_next_release()
            latest = pdf_data[-1] if pdf_data else None

            cache_payload = {
                "data": pdf_data,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": pdf_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "pdf",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": self._calculate_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_data_from_pdf(self) -> Optional[List[Dict[str, Any]]]:
        """
        財務省PDFからBEIデータを取得

        PDFの構造:
        - グラフ形式でデータが表示されている
        - 日付（例: 2026/1/22）とBEI値（例: 2.141%）がラベルとして表示
        - PDFのフォントは埋め込みフォントで日本語が文字化けするため、
          数値のみを座標ベースで抽出する
        """
        try:
            # PDFをダウンロード
            logger.info(f"Downloading BEI PDF from: {MOF_BEI_PDF_URL}")
            response = requests.get(
                MOF_BEI_PDF_URL,
                timeout=30,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            response.raise_for_status()

            # PDFをローカルに保存
            PDF_DIR.mkdir(parents=True, exist_ok=True)
            with open(PDF_FILE, 'wb') as f:
                f.write(response.content)
            logger.info(f"Saved BEI PDF to: {PDF_FILE}")

            # pdfplumberで解析
            try:
                import pdfplumber
            except ImportError:
                logger.error("pdfplumber not installed. Run: pip install pdfplumber")
                return None

            pdf_content = io.BytesIO(response.content)

            with pdfplumber.open(pdf_content) as pdf:
                if len(pdf.pages) == 0:
                    logger.warning("BEI PDF has no pages")
                    return None

                page = pdf.pages[0]
                chars = page.chars

                # 数値を座標ごとにグループ化して抽出
                number_groups = self._extract_number_groups(chars)

                # 日付を抽出
                date_str = None
                for group in number_groups:
                    match = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', group['text'])
                    if match:
                        year, month, day = match.groups()
                        date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                        break

                if not date_str:
                    logger.warning("Could not extract date from BEI PDF")
                    return None

                # BEI値を抽出（x.xxx形式の数値を探す）
                # PDFの構造:
                # - 1番目のx.xxx: 10年固定利付債 (例: 2.141%)
                # - 2番目のx.xxx: BEI（10年）(例: 1.915%)
                # - 3番目のx.xxx: 10年物価連動債 (例: 0.226%)
                bei_candidates = []
                for group in number_groups:
                    match = re.match(r'^(\d\.\d{3})%?$', group['text'])
                    if match:
                        bei_candidates.append({
                            'value': float(match.group(1)),
                            'y': group['y']
                        })

                # 各値を抽出
                fixed_rate_10y = bei_candidates[0]['value'] if len(bei_candidates) >= 1 else None
                bei_value = bei_candidates[1]['value'] if len(bei_candidates) >= 2 else None
                inflation_indexed_10y = bei_candidates[2]['value'] if len(bei_candidates) >= 3 else None

                if bei_value is not None:
                    logger.info(f"Found values - Fixed: {fixed_rate_10y}%, BEI: {bei_value}%, Inflation-indexed: {inflation_indexed_10y}%")
                else:
                    logger.warning("Could not extract BEI value from PDF")
                    return None

                # 単一のデータポイントを返す（このPDFは最新値のみを表示）
                data_point = {
                    "date": date_str,
                    "value": bei_value,
                    "fixed_rate_10y": fixed_rate_10y,
                    "inflation_indexed_10y": inflation_indexed_10y
                }

                logger.info(f"Extracted BEI data from PDF: {data_point}")

                # 既存のキャッシュデータがあれば、新しいデータを追加
                existing_data = self._load_file_cache()
                if existing_data and existing_data.get("data"):
                    # 既存データに新しいデータをマージ
                    data_list = existing_data["data"]
                    # 同じ日付のデータがあれば更新、なければ追加
                    found = False
                    for item in data_list:
                        if item["date"] == date_str:
                            item["value"] = bei_value
                            item["fixed_rate_10y"] = fixed_rate_10y
                            item["inflation_indexed_10y"] = inflation_indexed_10y
                            found = True
                            break
                    if not found:
                        data_list.append(data_point)
                    data_list.sort(key=lambda x: x["date"])
                    return data_list
                else:
                    return [data_point]

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download BEI PDF: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing BEI PDF: {e}", exc_info=True)
            return None

    def _extract_number_groups(self, chars: list) -> List[Dict[str, Any]]:
        """
        PDF文字列から数値グループを座標ベースで抽出

        Args:
            chars: pdfplumber.page.chars

        Returns:
            数値グループのリスト [{'text': '2026/1/22', 'y': 84.0}, ...]
        """
        number_groups = []
        current_group = {'chars': [], 'x': None, 'y': None}

        for char in sorted(chars, key=lambda c: (round(c['top'], 0), c['x0'])):
            text = char['text']
            x = char['x0']
            y = round(char['top'], 0)

            # 数字、ドット、マイナス、スラッシュ、パーセントのみ対象
            if text in '0123456789.-/%':
                if current_group['y'] != y or (current_group['x'] is not None and abs(x - current_group['x']) > 10):
                    # 新しいグループ開始
                    if current_group['chars']:
                        number_groups.append({
                            'text': ''.join(current_group['chars']),
                            'y': current_group['y']
                        })
                    current_group = {'chars': [text], 'x': x + char['width'], 'y': y}
                else:
                    current_group['chars'].append(text)
                    current_group['x'] = x + char['width']

        # 最後のグループを追加
        if current_group['chars']:
            number_groups.append({
                'text': ''.join(current_group['chars']),
                'y': current_group['y']
            })

        return number_groups

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        更新タイミング:
        - 毎週土曜日7:00 JST以降
        - 最終更新が前の土曜日以前の場合
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 今週の土曜日を計算
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0 and now.hour >= 7:
                # 今日が土曜日で7時以降
                this_saturday = now.replace(hour=7, minute=0, second=0, microsecond=0)
            elif days_until_saturday == 0:
                # 今日が土曜日だが7時前 -> 先週の土曜日を使用
                this_saturday = (now - timedelta(days=7)).replace(hour=7, minute=0, second=0, microsecond=0)
            else:
                # 先週の土曜日
                days_since_saturday = (now.weekday() - 5) % 7
                if days_since_saturday == 0:
                    days_since_saturday = 7
                this_saturday = (now - timedelta(days=days_since_saturday)).replace(hour=7, minute=0, second=0, microsecond=0)

            # 最終更新が今週の土曜日7時以前であれば更新
            if last_updated < this_saturday:
                logger.info(f"Cache needs refresh: last_updated={last_updated}, this_saturday={this_saturday}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking refresh status: {e}")
            return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を計算"""
        try:
            now = datetime.now(JST)

            # 次の土曜日を計算
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0 and now.hour >= 7:
                # 今日が土曜日で7時以降 -> 来週の土曜日
                days_until_saturday = 7

            next_saturday = now + timedelta(days=days_until_saturday)
            next_release = next_saturday.replace(hour=7, minute=0, second=0, microsecond=0)

            return {
                "date": next_release.strftime("%Y-%m-%d"),
                "time_jst": "07:00",
                "datetime_jst": next_release.isoformat()
            }

        except Exception as e:
            logger.error(f"Error calculating next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "10年物価連動国債BEI",
            "source": "MOF PDF",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
bei_service = BEIService()
