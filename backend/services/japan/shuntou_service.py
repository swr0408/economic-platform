"""
春闘サービス
連合（日本労働組合総連合会）の賃上げ交渉データを取得

指標:
- 春闘賃上げ率（加重平均）
- 各回速報データ

データソース:
- 経年データ: https://www.jtuc-rengo.or.jp/activity/roudou/shuntou/data/chinage_suii_first.zip
- プレスリリース: https://www.jtuc-rengo.or.jp/activity/roudou/shuntou/{yyyy}/yokyu_kaito/kaito/press_no{1~7}.pdf
- スケジュール: https://www.jtuc-rengo.or.jp/activity/roudou/shuntou/{yyyy}/houshin/data/tosokakunin{01~}.pdf

発表スケジュール:
- 不定期（2〜4月頃、計7回の速報発表）
- 毎週日曜日にスケジュールPDFを確認

キャッシュ方式: 独自更新判定方式（スケジュールPDFベース）
"""
import json
import logging
import re
import requests
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from io import BytesIO

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "shuntou_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "shuntou_schedule_cache.json"

# PDFディレクトリ
PDF_DIR = Path(__file__).parent.parent.parent / "data" / "pdf" / "japan" / "shuntou"
PDF_DIR.mkdir(parents=True, exist_ok=True)

# 連合URLベース
RENGO_BASE_URL = "https://www.jtuc-rengo.or.jp/activity/roudou/shuntou"


class ShuntouService:
    """春闘サービス"""

    DATA_CACHE_KEY = "japan:employment:shuntou:data"
    SCHEDULE_CACHE_KEY = "japan:employment:shuntou:schedule"

    # 経年データZIP URL
    HISTORICAL_DATA_URL = f"{RENGO_BASE_URL}/data/chinage_suii_first.zip"

    def __init__(self):
        pass

    def get_shuntou_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        春闘データを取得

        Returns:
            {
                "wage_increase": {"data": [...], "latest": {...}},  # 賃上げ率（加重平均）
                "union_member": {"data": [...], "latest": {...}},   # 組合員数賃上げ率（単純平均）
                "press_releases": [...],  # プレスリリース情報
                "next_release": {...},  # 次回発表情報
                "cached": bool,
                "source": str
            }
        """
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "wage_increase": cached_data.get("wage_increase"),
                        "union_member": cached_data.get("union_member"),
                        "press_releases": cached_data.get("press_releases", []),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 経年データをZIPから取得
        historical_data = self._load_historical_data()

        # プレスリリース情報を取得
        press_releases = self._get_press_releases()

        # 次回発表日時を取得
        next_release = self._get_next_release()

        if historical_data and (historical_data.get("wage_increase") or historical_data.get("union_member")):
            wage_increase_data = historical_data.get("wage_increase", [])
            union_member_data = historical_data.get("union_member", [])

            wage_increase = {
                "data": wage_increase_data,
                "latest": wage_increase_data[-1] if wage_increase_data else None,
            }
            union_member = {
                "data": union_member_data,
                "latest": union_member_data[-1] if union_member_data else None,
            }

            cache_payload = {
                "wage_increase": wage_increase,
                "union_member": union_member,
                "press_releases": press_releases,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                **cache_payload,
                "cached": False,
                "source": "rengo_zip",
            }

        # ファイルキャッシュからフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "wage_increase": file_cache.get("wage_increase"),
                "union_member": file_cache.get("union_member"),
                "press_releases": file_cache.get("press_releases", []),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "wage_increase": None,
            "union_member": None,
            "press_releases": [],
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_historical_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        経年データをZIPから取得

        ZIPファイル構造:
        - chinage_suii_first.zip
          - [Excelファイル] 賃上げ率の経年データ

        Returns:
            {
                "wage_increase": [...],  # 賃上げ率（加重平均）
                "union_member": [...]     # 組合員数賃上げ率（単純平均）
            }
        """
        try:
            logger.info(f"Downloading Shuntou historical data from: {self.HISTORICAL_DATA_URL}")

            response = requests.get(self.HISTORICAL_DATA_URL, timeout=60)
            if response.status_code != 200:
                logger.error(f"Failed to download Shuntou ZIP: {response.status_code}")
                return {"wage_increase": [], "union_member": []}

            # ZIPを解凍してExcelを読み込み
            with zipfile.ZipFile(BytesIO(response.content)) as zf:
                # ZIPファイル内のファイル一覧を取得
                file_list = zf.namelist()
                logger.info(f"ZIP contains: {file_list}")

                # Excelファイルを探す
                xlsx_files = [f for f in file_list if f.endswith('.xlsx') or f.endswith('.xls')]
                if xlsx_files:
                    return self._parse_excel_from_zip(zf, xlsx_files[0])

                # CSVファイルを探す（フォールバック）
                csv_files = [f for f in file_list if f.endswith('.csv')]
                if csv_files:
                    csv_content = zf.read(csv_files[0])
                    # CSVの場合は単一系列として返す
                    data = self._parse_csv_data(csv_content)
                    return {"wage_increase": data, "union_member": []}

                logger.error("No Excel or CSV file found in ZIP")
                return {"wage_increase": [], "union_member": []}

        except Exception as e:
            logger.error(f"Error loading Shuntou historical data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_csv_data(self, csv_content: bytes) -> List[Dict[str, Any]]:
        """
        CSVデータをパース

        想定フォーマット:
        年度, 賃上げ率(%), 参加組合数, ...
        """
        try:
            import pandas as pd
            from io import StringIO

            # エンコーディングを試行
            for encoding in ['utf-8', 'shift-jis', 'cp932', 'euc-jp']:
                try:
                    content = csv_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                logger.error("Could not decode CSV with any encoding")
                return []

            # CSVをパース
            df = pd.read_csv(StringIO(content), header=None)
            logger.info(f"CSV shape: {df.shape}")
            logger.info(f"CSV first rows:\n{df.head()}")

            result = []

            # ヘッダー行を探す
            start_row = 0
            for i in range(min(10, len(df))):
                row = df.iloc[i]
                if any('年' in str(cell) or '賃上げ' in str(cell) for cell in row if pd.notna(cell)):
                    start_row = i + 1
                    break

            # データ行を処理
            for i in range(start_row, len(df)):
                row = df.iloc[i]

                # 年度を取得（1列目）
                year_val = row.iloc[0]
                if pd.isna(year_val):
                    continue

                try:
                    # 年度を抽出（「2024年」「2024」「令和6年」など）
                    year_str = str(year_val)
                    year = self._extract_year(year_str)
                    if not year or year < 1955 or year > 2100:
                        continue
                except (ValueError, TypeError):
                    continue

                # 賃上げ率を取得（2列目）
                rate_val = row.iloc[1] if len(row) > 1 else None
                if pd.isna(rate_val):
                    continue

                try:
                    rate = float(str(rate_val).replace('%', '').strip())
                except (ValueError, TypeError):
                    continue

                # 参加組合数を取得（3列目、あれば）
                participants = None
                if len(row) > 2 and pd.notna(row.iloc[2]):
                    try:
                        participants = int(float(str(row.iloc[2]).replace(',', '')))
                    except (ValueError, TypeError):
                        pass

                result.append({
                    "date": f"{year}-01-01",  # 春闘は年度単位
                    "value": round(rate, 2),
                    "participants": participants
                })

            # 日付順でソート
            result.sort(key=lambda x: x["date"])

            logger.info(f"Parsed {len(result)} Shuntou data points")
            if result:
                logger.info(f"Date range: {result[0]['date']} to {result[-1]['date']}")
                logger.info(f"Latest: {result[-1]}")

            return result

        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_excel_from_zip(self, zf: zipfile.ZipFile, xlsx_file: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        ZIPからExcelファイルを読み込んでパース

        連合のExcelフォーマット:
        - 行0-2: 空白/タイトル
        - 行3: ヘッダー（年度、賃上げ率(%)、組合員数賃上げ率(%)）
        - 行4以降: データ（年度は2桁: 89=1989, 00=2000, 01=2001...）

        Returns:
            {
                "wage_increase": [...],  # 賃上げ率
                "union_member": [...]     # 組合員数賃上げ率
            }
        """
        try:
            import pandas as pd
            from io import BytesIO

            xlsx_content = zf.read(xlsx_file)
            df = pd.read_excel(BytesIO(xlsx_content), header=None)
            logger.info(f"Excel shape: {df.shape}")

            wage_increase = []  # 賃上げ率（加重平均）
            union_member = []   # 組合員数賃上げ率（単純平均）

            # データ行を処理（行4から開始、2桁年度形式）
            for i in range(4, len(df)):
                row = df.iloc[i]

                year_val = row.iloc[0]
                if pd.isna(year_val):
                    continue

                # 2桁年度を西暦に変換
                year = self._convert_two_digit_year(year_val)
                if not year:
                    continue

                date_str = f"{year}-01-01"

                # 賃上げ率（列1）
                rate_val = row.iloc[1] if len(row) > 1 else None
                if pd.notna(rate_val):
                    try:
                        rate = float(str(rate_val).replace('%', '').strip())
                        wage_increase.append({
                            "date": date_str,
                            "value": round(rate, 2),
                        })
                    except (ValueError, TypeError):
                        pass

                # 組合員数賃上げ率（列2）
                union_rate_val = row.iloc[2] if len(row) > 2 else None
                if pd.notna(union_rate_val):
                    try:
                        union_rate = float(str(union_rate_val).replace('%', '').strip())
                        union_member.append({
                            "date": date_str,
                            "value": round(union_rate, 2),
                        })
                    except (ValueError, TypeError):
                        pass

            wage_increase.sort(key=lambda x: x["date"])
            union_member.sort(key=lambda x: x["date"])

            logger.info(f"Parsed {len(wage_increase)} wage_increase, {len(union_member)} union_member data points")
            if wage_increase:
                logger.info(f"Date range: {wage_increase[0]['date']} to {wage_increase[-1]['date']}")
                logger.info(f"Latest wage_increase: {wage_increase[-1]}")

            return {
                "wage_increase": wage_increase,
                "union_member": union_member,
            }

        except Exception as e:
            logger.error(f"Error parsing Excel from ZIP: {e}")
            import traceback
            traceback.print_exc()
            return {"wage_increase": [], "union_member": []}

    def _convert_two_digit_year(self, year_val) -> Optional[int]:
        """
        2桁年度を西暦に変換

        連合データフォーマット:
        - 89, 90, ..., 99 → 1989, 1990, ..., 1999
        - 00, 01, ..., 25 → 2000, 2001, ..., 2025
        - '00', '01' などの文字列も対応
        """
        try:
            # 文字列の場合は数値に変換
            year_str = str(year_val).strip().replace("'", "")

            # 整数に変換
            year_num = int(float(year_str))

            # 2桁年度の場合
            if 0 <= year_num <= 99:
                if year_num >= 89:
                    # 89-99 → 1989-1999
                    return 1900 + year_num
                else:
                    # 00-88 → 2000-2088
                    return 2000 + year_num

            # 4桁年度の場合はそのまま返す
            if 1900 <= year_num <= 2100:
                return year_num

            return None

        except (ValueError, TypeError):
            return None

    def _extract_year(self, year_str: str) -> Optional[int]:
        """
        年度文字列から西暦を抽出

        対応フォーマット:
        - "2024", "2024年"
        - "令和6年", "R6"
        - "平成31年", "H31"
        - "昭和64年", "S64"
        """
        year_str = str(year_str).strip()

        # 西暦の場合
        match = re.search(r'(\d{4})', year_str)
        if match:
            return int(match.group(1))

        # 令和
        match = re.search(r'令和\s*(\d+)', year_str)
        if match:
            return 2018 + int(match.group(1))

        match = re.search(r'R\s*(\d+)', year_str, re.IGNORECASE)
        if match:
            return 2018 + int(match.group(1))

        # 平成
        match = re.search(r'平成\s*(\d+)', year_str)
        if match:
            return 1988 + int(match.group(1))

        match = re.search(r'H\s*(\d+)', year_str, re.IGNORECASE)
        if match:
            return 1988 + int(match.group(1))

        # 昭和
        match = re.search(r'昭和\s*(\d+)', year_str)
        if match:
            return 1925 + int(match.group(1))

        match = re.search(r'S\s*(\d+)', year_str, re.IGNORECASE)
        if match:
            return 1925 + int(match.group(1))

        return None

    def _get_press_releases(self) -> List[Dict[str, Any]]:
        """
        プレスリリース情報を取得

        404ページ検知: 連合サイトは404でも200を返しリダイレクトするため、
        - Content-Typeがapplication/pdfか確認
        - URLがPDFのままか確認（404.htmlにリダイレクトされていないか）

        PDFキャッシュ:
        - 有効なPDFはローカルにキャッシュ
        - キャッシュがあればURLチェックをスキップ

        Returns:
            [{
                "number": 1,  # 第何回速報
                "url": "https://...",  # PDF URL
                "year": 2024,
                "title": "第1回回答集計結果",
                "cached": bool,  # ローカルキャッシュの有無
            }, ...]
        """
        try:
            now = datetime.now(JST)
            year = now.year

            press_releases = []

            # 第1回〜第7回のプレスリリースをチェック
            for i in range(1, 8):
                url = f"{RENGO_BASE_URL}/{year}/yokyu_kaito/kaito/press_no{i}.pdf"
                cached_path = self._get_pdf_cache_path(year, i)

                # キャッシュがあればスキップ
                if cached_path.exists():
                    press_releases.append({
                        "number": i,
                        "url": url,
                        "year": year,
                        "title": f"第{i}回回答集計結果",
                        "cached": True,
                    })
                    continue

                # URLチェックしてキャッシュ
                if self._is_valid_pdf_url(url):
                    self._cache_pdf(url, year, i)
                    press_releases.append({
                        "number": i,
                        "url": url,
                        "year": year,
                        "title": f"第{i}回回答集計結果",
                        "cached": True,
                    })

            # 去年のプレスリリースもチェック（1月頃の場合）
            if now.month <= 2:
                prev_year = year - 1
                for i in range(1, 8):
                    url = f"{RENGO_BASE_URL}/{prev_year}/yokyu_kaito/kaito/press_no{i}.pdf"
                    cached_path = self._get_pdf_cache_path(prev_year, i)

                    # キャッシュがあればスキップ
                    if cached_path.exists():
                        if not any(pr["year"] == prev_year and pr["number"] == i for pr in press_releases):
                            press_releases.append({
                                "number": i,
                                "url": url,
                                "year": prev_year,
                                "title": f"第{i}回回答集計結果",
                                "cached": True,
                            })
                        continue

                    if self._is_valid_pdf_url(url):
                        self._cache_pdf(url, prev_year, i)
                        # 既に今年のものがあれば去年のは追加しない
                        if not any(pr["year"] == prev_year and pr["number"] == i for pr in press_releases):
                            press_releases.append({
                                "number": i,
                                "url": url,
                                "year": prev_year,
                                "title": f"第{i}回回答集計結果",
                                "cached": True,
                            })

            logger.info(f"Found {len(press_releases)} press releases")
            return press_releases

        except Exception as e:
            logger.error(f"Error getting press releases: {e}")
            return []

    def _get_pdf_cache_path(self, year: int, number: int) -> Path:
        """PDFキャッシュパスを取得"""
        return PDF_DIR / f"{year}_press_no{number}.pdf"

    def _cache_pdf(self, url: str, year: int, number: int) -> bool:
        """PDFをローカルにキャッシュ"""
        try:
            response = requests.get(url, timeout=60)
            if response.status_code != 200:
                return False

            # Content-Typeチェック
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' not in content_type and not url.endswith('.pdf'):
                return False

            cache_path = self._get_pdf_cache_path(year, number)
            PDF_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"Cached PDF: {cache_path}")
            return True

        except Exception as e:
            logger.error(f"Error caching PDF: {e}")
            return False

    def _is_valid_pdf_url(self, url: str) -> bool:
        """
        URLが有効なPDFファイルかどうかを確認

        連合サイトは404ページにリダイレクトして200を返すため、
        以下の方法で検証:
        1. HEADリクエストでContent-Typeがapplication/pdfか確認
        2. リダイレクト後のURLが404.htmlでないか確認
        """
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)

            if response.status_code != 200:
                return False

            # リダイレクト先URLが404.htmlの場合は無効
            if '404' in response.url:
                return False

            # Content-Typeがapplication/pdfか確認
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' in content_type:
                return True

            # Content-Typeがない場合、拡張子で判断
            if response.url.endswith('.pdf'):
                return True

            return False

        except requests.RequestException:
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日時を取得

        - 毎週日曜日18:00にスケジュールPDFを確認
        - 7回目発表後はその年はスキップし、来年2月を推定
        """
        try:
            now = datetime.now(JST)

            # 7回目発表済みかチェック（現在のキャッシュから）
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                press_releases = cached_data.get("press_releases", [])
                current_year_releases = [pr for pr in press_releases if pr.get("year") == now.year]
                has_7th_release = any(pr.get("number") == 7 for pr in current_year_releases)

                if has_7th_release and now.month >= 5:
                    # 7回目発表済みで5月以降なら、来年2月を推定（16:00開始）
                    next_year = now.year + 1
                    return {
                        "date": datetime(next_year, 2, 15, 16, 0, tzinfo=JST).isoformat(),
                        "label": f"{next_year}年春闘開始予定",
                        "estimated": True
                    }

            # スケジュールキャッシュを確認
            cached_schedule = redis_client.get(self.SCHEDULE_CACHE_KEY)
            if cached_schedule:
                last_checked = cached_schedule.get("last_checked")
                if last_checked:
                    last_checked_dt = datetime.fromisoformat(last_checked)
                    # 日曜日18:00以降でなければキャッシュを使用
                    sunday_18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
                    if now.weekday() != 6 or now < sunday_18:
                        # 1週間以内ならキャッシュを使用
                        if (now - last_checked_dt).days < 7:
                            return cached_schedule.get("next_release")
                    # 日曜日18:00以降で、最終チェックが今週日曜18:00より前ならチェック
                    elif last_checked_dt >= sunday_18:
                        # 今週既にチェック済みならキャッシュを使用
                        return cached_schedule.get("next_release")

            # スケジュールPDFを確認
            schedule = self._check_schedule_pdf()

            if schedule:
                cache_payload = {
                    "next_release": schedule,
                    "last_checked": datetime.now(JST).isoformat()
                }
                redis_client.set(self.SCHEDULE_CACHE_KEY, cache_payload, expire=0)
                self._save_schedule_cache(cache_payload)
                return schedule

            # スケジュールが見つからない場合
            return self._estimate_next_release()

        except Exception as e:
            logger.error(f"Error getting next release: {e}")
            return self._estimate_next_release()

    def _check_schedule_pdf(self) -> Optional[Dict[str, Any]]:
        """
        スケジュールPDFから次回発表日時を取得

        URL: https://www.jtuc-rengo.or.jp/activity/roudou/shuntou/{yyyy}/houshin/data/tosokakunin{01~}.pdf

        連合サイトは404でも200を返すため、Content-Typeとリダイレクト先URLをチェック
        """
        try:
            now = datetime.now(JST)
            year = now.year

            # 最新のスケジュールPDFを探す（20から1まで逆順でチェック）
            latest_pdf_url = None
            for i in range(20, 0, -1):
                url = f"{RENGO_BASE_URL}/{year}/houshin/data/tosokakunin{i:02d}.pdf"
                try:
                    response = requests.head(url, timeout=10, allow_redirects=True)
                    if response.status_code != 200:
                        continue
                    # 404ページへのリダイレクトチェック
                    if '404' in response.url:
                        continue
                    # Content-Typeチェック
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/pdf' in content_type or response.url.endswith('.pdf'):
                        latest_pdf_url = url
                        logger.info(f"Found schedule PDF: tosokakunin{i:02d}.pdf")
                        break
                except requests.RequestException:
                    continue

            if not latest_pdf_url:
                logger.info("No schedule PDF found")
                return None

            # PDFをダウンロードして解析
            response = requests.get(latest_pdf_url, timeout=60)
            if response.status_code != 200:
                return None

            # Content-Typeを再確認
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' not in content_type:
                logger.warning(f"Schedule PDF has invalid Content-Type: {content_type}")
                return None

            # PDFからスケジュールを抽出
            schedule = self._extract_schedule_from_pdf(BytesIO(response.content))
            return schedule

        except Exception as e:
            logger.error(f"Error checking schedule PDF: {e}")
            return None

    def _extract_schedule_from_pdf(self, pdf_content: BytesIO) -> Optional[Dict[str, Any]]:
        """
        PDFからスケジュール情報を抽出

        連合スケジュールPDFフォーマット:
        - 「N月 N日 ... 第N回回答集計結果公表」形式
        - 月が省略される場合あり（前の行の月を継承）
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed, cannot read PDF")
            return None

        try:
            with pdfplumber.open(pdf_content) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

                if not text:
                    return None

                now = datetime.now(JST)
                year = now.year

                releases = []
                lines = text.split("\n")
                current_month = None

                for line in lines:
                    # 「N月」を検出して現在の月を更新
                    month_match = re.search(r'(\d{1,2})月', line)
                    if month_match:
                        current_month = int(month_match.group(1))

                    # 「第N回回答集計」を含む行を探す
                    if '回答集計' not in line:
                        continue

                    # 「N月 N日 ... 第N回回答集計」パターン
                    full_match = re.search(r'(\d{1,2})月\s*(\d{1,2})日.*?第(\d+)回回答集計', line)
                    if full_match:
                        month, day, number = full_match.groups()
                        current_month = int(month)
                        try:
                            date = datetime(year, int(month), int(day), 16, 0, tzinfo=JST)
                            releases.append({
                                "number": int(number),
                                "date": date.isoformat(),
                            })
                            logger.info(f"Found schedule: 第{number}回 {month}/{day}")
                        except (ValueError, TypeError):
                            pass
                        continue

                    # 「N日 ... 第N回回答集計」パターン（月が省略）
                    day_match = re.search(r'^(\d{1,2})日.*?第(\d+)回回答集計', line)
                    if day_match and current_month:
                        day, number = day_match.groups()
                        try:
                            date = datetime(year, current_month, int(day), 16, 0, tzinfo=JST)
                            releases.append({
                                "number": int(number),
                                "date": date.isoformat(),
                            })
                            logger.info(f"Found schedule: 第{number}回 {current_month}/{day}")
                        except (ValueError, TypeError):
                            pass

                if not releases:
                    logger.info("No schedule found in PDF")
                    return None

                # 現在より未来の日付のうち最も近いものを返す
                future_releases = [
                    r for r in releases
                    if datetime.fromisoformat(r["date"]) > now
                ]

                if future_releases:
                    future_releases.sort(key=lambda x: x["date"])
                    next_release = future_releases[0]
                    return {
                        "date": next_release["date"],
                        "label": f"第{next_release['number']}回速報"
                    }

                logger.info("All scheduled releases are in the past")
                return None

        except Exception as e:
            logger.error(f"Error extracting schedule from PDF: {e}")
            return None

    def _estimate_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日時を推定（スケジュールPDFが見つからない場合）

        春闘は通常2月〜4月に集中
        データ更新チェック時間: 16:00, 16:30, 17:00, 17:30, 18:00
        """
        now = datetime.now(JST)
        year = now.year

        # 現在の月に基づいて推定
        if now.month < 2:
            # 1月: 2月中旬を推定（16:00開始）
            next_date = datetime(year, 2, 15, 16, 0, tzinfo=JST)
        elif now.month <= 4:
            # 2〜4月: 次の金曜日を推定（発表は通常金曜日、16:00開始）
            days_until_friday = (4 - now.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            next_date = now + timedelta(days=days_until_friday)
            next_date = next_date.replace(hour=16, minute=0, second=0, microsecond=0)
        elif now.month <= 6:
            # 5〜6月: 最終集計を推定
            next_date = datetime(year, 7, 1, 16, 0, tzinfo=JST)
        else:
            # 7月以降: 来年の2月を推定
            next_date = datetime(year + 1, 2, 15, 16, 0, tzinfo=JST)

        return {
            "date": next_date.isoformat(),
            "label": "推定",
            "estimated": True
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        更新タイミング:
        1. 毎週日曜日18:00: スケジュールPDFチェック（次回発表日時取得）
        2. 発表日当日: 16:00, 16:30, 17:00, 17:30, 18:00の5回チェック
        3. 7回目発表後はその年はスキップ
        4. 最新PDFが取得できたら次回発表までスキップ
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # キャッシュから次回発表日時を取得
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                next_release = cached_data.get("next_release")
                press_releases = cached_data.get("press_releases", [])

                # 7回目発表済みかチェック
                current_year_releases = [pr for pr in press_releases if pr.get("year") == now.year]
                has_7th_release = any(pr.get("number") == 7 for pr in current_year_releases)

                if has_7th_release:
                    # 7回目発表済みの場合、その年は更新しない（来年1月まで）
                    if now.month >= 5:  # 5月以降は来年まで更新しない
                        logger.info("7th press release already published, skipping updates until next year")
                        return False

                # 次回発表日時の当日かチェック
                if next_release and next_release.get("date"):
                    next_release_dt = datetime.fromisoformat(next_release["date"])
                    if next_release_dt.tzinfo is None:
                        next_release_dt = next_release_dt.replace(tzinfo=JST)

                    # 発表日当日の場合、16:00〜18:00の5回チェック
                    if now.date() == next_release_dt.date():
                        check_times = [
                            (16, 0), (16, 30), (17, 0), (17, 30), (18, 0)
                        ]
                        for hour, minute in check_times:
                            check_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                            # チェック時間を過ぎていて、最終更新がそれより前なら更新
                            if now >= check_time and last_updated < check_time:
                                logger.info(f"Release day check time passed ({check_time}), refreshing data")
                                return True

            # 毎週日曜日18:00: スケジュールPDFチェック用
            if now.weekday() == 6:  # 日曜日
                sunday_18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
                if now >= sunday_18 and last_updated < sunday_18:
                    logger.info(f"Sunday 18:00 schedule check time passed, refreshing data")
                    return True

            # 7日以上経過していれば更新
            if (now - last_updated).days >= 7:
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking refresh status: {e}")
            return True

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
            logger.info(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def _save_schedule_cache(self, data: Dict[str, Any]) -> None:
        """スケジュールキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save schedule cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "春闘 (Shuntou)",
            "source": "連合 (JTUC-Rengo)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "press_releases_count": len(cached_data.get("press_releases", [])) if cached_data else 0,
            "next_release": cached_data.get("next_release") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
shuntou_service = ShuntouService()
