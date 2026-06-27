"""
SNBインフレ見通しサービス
SNBプレスリリースからインフレ見通し画像を取得

指標:
- 実績インフレ率 (Observed Inflation)
- 条件付きインフレ見通し (Conditional Inflation Forecast)

データソース:
- SNBプレスリリースのPNG画像

発表スケジュール:
- 不定期（年4回程度、SNB金利決定と同時）
- 発表時刻: 08:30 チューリッヒ時間

キャッシュ方式: FMP発表日時ベース判定方式（SNB Interest Rate Decisionを使用）
"""
import json
import httpx
from datetime import datetime
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.switzerland.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
    resolve_last_updated_after_fetch,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_CACHE_DIR = CACHE_DIR / "inflation_forecast_images"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_inflation_forecast_cache.json"


class ChInflationForecastService:
    """SNBインフレ見通しサービス"""

    DATA_CACHE_KEY = "switzerland:ch_inflation_forecast:data"
    FMP_EVENT_PATTERN = "SNB Interest Rate Decision"

    def __init__(self):
        pass

    def get_inflation_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """SNBインフレ見通しデータを取得（最新分のみ）"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country="CH")

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # DBから直近の発表日を取得し、画像をダウンロード
        latest = self._fetch_latest_release()

        if latest:
            # 発表時刻レース対策（ラグガード）: 最新発表日が前回から進んでいない
            # （SNB画像が未公開等）場合は last_updated を発表直前に据え置き、
            # 公開後の次ポーリングでの再取得を促す。
            _prev_cache = redis_client.get(self.DATA_CACHE_KEY)
            _prev_latest = _prev_cache.get("latest") if isinstance(_prev_cache, dict) else None
            _resolved_last_updated = resolve_last_updated_after_fetch(
                self.FMP_EVENT_PATTERN,
                latest.get("release_date") if isinstance(latest, dict) else None,
                _prev_latest.get("release_date") if isinstance(_prev_latest, dict) else None,
                _prev_cache.get("last_updated") if isinstance(_prev_cache, dict) else None,
                country="CH",
            )

            cache_payload = {
                "latest": latest,
                "metadata": {
                    "source": "Swiss National Bank",
                    "indicator": "SNB Inflation Forecast",
                    "description": "SNBインフレ見通し（条件付き予測）",
                },
                "last_updated": _resolved_last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "snb",
                "last_updated": _resolved_last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _get_latest_release_date_from_db(self) -> Optional[str]:
        """直近のSNB金融政策発表日を取得（DB優先、SNBカレンダーICSにフォールバック）

        SNBインフレ見通しの画像は発表時刻に公開される。FMPのactual取り込みが
        遅れても画像は既に存在するため、判定は datetime_utc <= NOW() で行う。
        actual IS NOT NULL で絞ると、FMPバックフィル遅延中に旧イベントが返る不具合の原因になる。
        """
        # 1. DB（economic_calendar_events）から取得
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc
                    FROM economic_calendar_events
                    WHERE country = 'CH'
                      AND event ILIKE '%SNB Interest Rate Decision%'
                      AND datetime_utc <= NOW()
                    ORDER BY datetime_utc DESC
                    LIMIT 1
                """)
                row = session.execute(query).fetchone()

                if row and row[0]:
                    return row[0].strftime("%Y%m%d")

        except Exception as e:
            print(f"[ChInflationForecast] Error getting latest release date from DB: {e}")

        # 2. SNBカレンダー（ICS）にフォールバック
        return self._get_latest_release_date_from_calendar()

    def _get_latest_release_date_from_calendar(self) -> Optional[str]:
        """SNBカレンダー（ICS）から直近の金融政策発表日（過去）を取得"""
        try:
            from services.switzerland.snb_calendar_service import snb_calendar_service

            schedule = snb_calendar_service._get_schedule()
            events = schedule.get("monetary_policy_decision", []) if schedule else []
            if not events:
                print("[ChInflationForecast] SNB calendar has no monetary_policy_decision events")
                return None

            now = datetime.now(JST)
            latest_dt: Optional[datetime] = None

            for event in events:
                dt_str = event.get("datetime")
                if not dt_str:
                    continue
                try:
                    event_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    continue
                # ZURICH時刻として解釈、JST比較
                event_dt_zurich = event_dt.replace(tzinfo=ZoneInfo("Europe/Zurich"))
                if event_dt_zurich > now:
                    continue
                if latest_dt is None or event_dt_zurich > latest_dt:
                    latest_dt = event_dt_zurich

            if latest_dt:
                return latest_dt.strftime("%Y%m%d")

            return None

        except Exception as e:
            print(f"[ChInflationForecast] Error getting latest release date from calendar: {e}")
            return None

    def _generate_image_urls(self, release_date: str) -> Dict[str, str]:
        """
        発表日からPNG画像URLを動的生成

        標準パターン:
        - observed: pre_{date}/publications2_en/pre_{date}_p2.en.png
        - forecast: pre_{date}/publications3_en/pre_{date}_p3.en.png
        """
        base_url = f"https://www.snb.ch/public/asset/en/www-snb-ch/publications/communication/press-releases-restricted/pre_{release_date}"

        return {
            "observed_url": f"{base_url}/publications2_en/pre_{release_date}_p2.en.png",
            "forecast_url": f"{base_url}/publications3_en/pre_{release_date}_p3.en.png",
        }

    def _fetch_latest_release(self) -> Optional[Dict[str, Any]]:
        """最新のリリース画像をダウンロードしてキャッシュ"""
        # DBから直近の発表日を取得
        release_date = self._get_latest_release_date_from_db()

        if not release_date:
            print("[ChInflationForecast] No release date found in DB")
            return None

        # URL生成
        urls = self._generate_image_urls(release_date)
        observed_url = urls["observed_url"]
        forecast_url = urls["forecast_url"]

        # ローカルファイルパス
        observed_local = IMAGE_CACHE_DIR / f"{release_date}_observed.png"
        forecast_local = IMAGE_CACHE_DIR / f"{release_date}_forecast.png"

        # 画像をダウンロード
        observed_ok = self._download_image(observed_url, observed_local)
        forecast_ok = self._download_image(forecast_url, forecast_local)

        # 標準PNG(p2/p3)が未公開(404)なら、PDF(publications0)埋め込みチャートで補完。
        # SNBはPDFを発表時刻に公開するが、個別チャートPNGは後追いのことがあるため
        # (2026-06-18の6月会合で実測: PDFのみ公開、p2/p3は404)。
        if not (observed_ok and forecast_ok):
            pdf_res = self._fetch_from_pdf(
                release_date, observed_local, forecast_local,
                need_observed=not observed_ok, need_forecast=not forecast_ok,
            )
            observed_ok = observed_ok or pdf_res.get("observed", False)
            forecast_ok = forecast_ok or pdf_res.get("forecast", False)

        if observed_ok or forecast_ok:
            # 日付を整形
            formatted_date = f"{release_date[:4]}-{release_date[4:6]}-{release_date[6:]}"

            return {
                "release_date": formatted_date,
                "observed_image": f"/api/switzerland/snb/inflation-forecast/image/{release_date}_observed.png" if observed_ok else None,
                "forecast_image": f"/api/switzerland/snb/inflation-forecast/image/{release_date}_forecast.png" if forecast_ok else None,
                "observed_url": observed_url,
                "forecast_url": forecast_url,
            }

        return None

    def _download_image(self, url: str, local_path: Path) -> bool:
        """画像をダウンロード（既にあればスキップ）"""
        if local_path.exists():
            return True

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    local_path.write_bytes(response.content)
                    print(f"[ChInflationForecast] Downloaded: {local_path.name}")
                    return True
                else:
                    print(f"[ChInflationForecast] Failed to download {url}: {response.status_code}")
                    return False
        except Exception as e:
            print(f"[ChInflationForecast] Error downloading {url}: {e}")
            return False

    def _fetch_from_pdf(
        self,
        release_date: str,
        observed_local: Path,
        forecast_local: Path,
        need_observed: bool,
        need_forecast: bool,
    ) -> Dict[str, bool]:
        """標準PNG(p2/p3)が未公開のとき、SNBプレスリリースPDF(publications0)に
        埋め込まれたチャート画像を抽出してフォールバックする。

        SNBはPDFを発表時刻に公開するが、個別チャートPNGの公開は後追いのことがある
        (2026-06-18の6月会合で実測)。PDF埋め込み画像は website 配信PNGと同一チャート
        (寸法一致を確認済み)。判定: p2(observed)/p3(forecast)は幅≈2141の横長PNG。
        forecast(扇形予測)はobservedより縦が高くアスペクト比が小さいため、幅の広い
        候補のうちアスペクト比 最小=forecast / 最大=observed とする。
        """
        result = {"observed": False, "forecast": False}
        try:
            import fitz  # PyMuPDF
        except Exception as e:
            print(f"[ChInflationForecast] PDF fallback: PyMuPDF unavailable: {e}")
            return result

        urls = self._generate_image_urls(release_date)
        base = urls["observed_url"].rsplit("/publications", 1)[0]
        pdf_url = f"{base}/publications0_en/pre_{release_date}.en.pdf"

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(pdf_url)
            if resp.status_code != 200:
                print(f"[ChInflationForecast] PDF fallback: PDF not available ({resp.status_code})")
                return result
            doc = fitz.open(stream=resp.content, filetype="pdf")
        except Exception as e:
            print(f"[ChInflationForecast] PDF fallback download/open error: {e}")
            return result

        wide = []  # (aspect, width, height, png_bytes)
        try:
            for page in doc:
                for img in page.get_images(full=True):
                    try:
                        info = doc.extract_image(img[0])
                    except Exception:
                        continue
                    if info.get("ext") != "png":
                        continue
                    w, h = info.get("width", 0), info.get("height", 0)
                    # p1(幅1890)やロゴを除外し、p2/p3(幅≈2141)の横長チャートのみ採用
                    if not w or not h or w < 2000:
                        continue
                    wide.append((w / h, w, h, info["image"]))
        finally:
            doc.close()

        if not wide:
            print("[ChInflationForecast] PDF fallback: no chart images found in PDF")
            return result

        wide.sort(key=lambda t: t[0])  # アスペクト比 昇順
        forecast_img = wide[0]                       # 最小=forecast(縦長)
        observed_img = wide[-1]                       # 最大=observed(横長)

        if need_forecast:
            try:
                forecast_local.write_bytes(forecast_img[3])
                result["forecast"] = True
                print(f"[ChInflationForecast] PDF fallback: forecast extracted "
                      f"({forecast_img[1]}x{forecast_img[2]})")
            except Exception as e:
                print(f"[ChInflationForecast] PDF fallback forecast save error: {e}")

        if need_observed and observed_img is not forecast_img:
            try:
                observed_local.write_bytes(observed_img[3])
                result["observed"] = True
                print(f"[ChInflationForecast] PDF fallback: observed extracted "
                      f"({observed_img[1]}x{observed_img[2]})")
            except Exception as e:
                print(f"[ChInflationForecast] PDF fallback observed save error: {e}")

        return result

    def get_image(self, filename: str) -> Optional[bytes]:
        """キャッシュされた画像を取得"""
        filepath = IMAGE_CACHE_DIR / filename
        if filepath.exists():
            return filepath.read_bytes()
        return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country="CH"
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ChInflationForecast] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ChInflationForecast] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        # キャッシュされた画像ファイル数をカウント
        image_count = len(list(IMAGE_CACHE_DIR.glob("*.png"))) if IMAGE_CACHE_DIR.exists() else 0

        return {
            "indicator": "SNB Inflation Forecast",
            "source": "Swiss National Bank",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country="CH"),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "cached_images_count": image_count,
        }


# シングルトンインスタンス
ch_inflation_forecast_service = ChInflationForecastService()
