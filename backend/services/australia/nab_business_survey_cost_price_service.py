"""
NAB企業調査 コスト・価格指標 サービス（PDF画像切り出し方式）
NAB Monthly Business Survey - Cost & Price Chart Screenshots

PDFのPage 4からChart 18 (Cost Growth) とChart 20 (Output Price Growth) を画像として切り出す

指標:
- Chart 18: Cost Growth, SA (% Qtly Eq.) — Purchase Costs + Labour Costs
- Chart 20: Output Price Growth, SA (% Qtly Eq.) — Product Price + Retail Price

データソース:
- PDF: backend/data/manual_update/monthly/australia_nab/NAB-Monthly-Business-Survey-*.pdf（手動配置）
- FMP API: next_release のみ（NAB Business Confidence パターン）

発表スケジュール: 毎月（NAB Business Confidence と同時）
"""
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.australia.fmp_next_release_utils import (
    get_next_release_by_pattern,
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ（画像保存先）
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "australia" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# PDFディレクトリ
PDF_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "monthly" / "australia_nab"

# FMPパターン（next_release取得用）
FMP_EVENT_PATTERN = "NAB Business Confidence"
FMP_COUNTRY = "AU"

# スクリーンショット設定
SCREENSHOTS = {
    "cost_growth": {
        "filename": "nab_chart18_cost_growth.png",
        "label": "Cost Growth, SA (% Qtly Eq.)",
        "label_ja": "仕入れコスト・雇用コスト",
    },
    "output_price_growth": {
        "filename": "nab_chart20_output_price_growth.png",
        "label": "Output Price Growth, SA (% Qtly Eq.)",
        "label_ja": "販売価格・製品価格",
    },
}

# 処理済みPDFトラッキングファイル
IMPORTED_PDF_FILE = CACHE_DIR / "nab_imported_pdfs.json"


class NabBusinessSurveyCostPriceService:
    """NAB企業調査 コスト・価格指標サービス（PDF画像切り出し方式）"""

    CACHE_KEY = "australia:nab_cost_price_screenshot:metadata"

    def __init__(self):
        pass

    def _find_latest_pdf(self) -> Optional[Path]:
        """最新のNAB PDFファイルを探す"""
        if not PDF_DIR.exists():
            logger.warning(f"[NabCostPrice] PDF directory not found: {PDF_DIR}")
            return None

        pdf_files = list(PDF_DIR.glob("NAB-Monthly-Business-Survey-*.pdf"))
        if not pdf_files:
            logger.info("[NabCostPrice] No NAB PDF files found")
            return None

        # ファイル名でソート（降順 → 最新が先頭）
        pdf_files.sort(key=lambda p: p.name, reverse=True)
        return pdf_files[0]

    def _extract_charts_from_pdf(self, pdf_path: Path) -> bool:
        """
        PDFのPage 4からChart 18とChart 20を画像として切り出す

        Page 4 レイアウト（座標はpdfplumberで確認済み）:
        - Chart 18 (Cost Growth): タイトルy=253.5, 画像y=263.8〜413.3
        - Chart 20 (Output Price Growth): タイトルy=425.1, 画像y=435.3〜589.3
        """
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) < 4:
                    logger.warning(f"[NabCostPrice] PDF has only {len(pdf.pages)} pages, need at least 4")
                    return False

                page = pdf.pages[3]  # Page 4 (0-indexed)

                # ページ内のテキストからChart 18, 20の位置を動的に検出
                chart18_title_y, chart20_title_y = self._find_chart_positions(page)

                if chart18_title_y is None or chart20_title_y is None:
                    logger.warning("[NabCostPrice] Could not find chart positions, using defaults")
                    chart18_title_y = 253.5
                    chart20_title_y = 425.1

                # 高解像度で画像化
                page_image = page.to_image(resolution=200)
                pil_image = page_image.original
                scale = 200 / 72

                # Chart 18: Cost Growth
                chart18_bbox = (
                    int(42 * scale),
                    int((chart18_title_y - 3) * scale),
                    int(295 * scale),
                    int((chart20_title_y - 8) * scale),
                )
                chart18_img = pil_image.crop(chart18_bbox)
                chart18_path = CACHE_DIR / SCREENSHOTS["cost_growth"]["filename"]
                chart18_img.save(str(chart18_path))
                logger.info(f"[NabCostPrice] Chart 18 saved: {chart18_path} ({chart18_img.size})")

                # Chart 20: Output Price Growth
                # ページ下端まで（ただしページ番号は除く）
                page_bottom = min(page.height - 25, chart20_title_y + 170)
                chart20_bbox = (
                    int(42 * scale),
                    int((chart20_title_y - 3) * scale),
                    int(295 * scale),
                    int(page_bottom * scale),
                )
                chart20_img = pil_image.crop(chart20_bbox)
                chart20_path = CACHE_DIR / SCREENSHOTS["output_price_growth"]["filename"]
                chart20_img.save(str(chart20_path))
                logger.info(f"[NabCostPrice] Chart 20 saved: {chart20_path} ({chart20_img.size})")

            return True

        except ImportError:
            logger.error("[NabCostPrice] pdfplumber not installed")
            return False
        except Exception as e:
            logger.error(f"[NabCostPrice] Error extracting charts from PDF: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_chart_positions(self, page) -> tuple:
        """ページ内のテキストからChart 18, 20のY座標を検出"""
        chart18_y = None
        chart20_y = None

        words = page.extract_words()
        for i, w in enumerate(words):
            if w['text'] == 'Chart' and i + 1 < len(words):
                next_text = words[i + 1]['text']
                if next_text == '18:':
                    chart18_y = w['top']
                elif next_text == '20:':
                    chart20_y = w['top']

        return chart18_y, chart20_y

    def check_and_extract(self) -> bool:
        """新しいPDFがあれば画像を切り出す"""
        latest_pdf = self._find_latest_pdf()
        if not latest_pdf:
            return False

        # 処理済みチェック
        imported = self._load_imported_pdfs()
        pdf_key = f"{latest_pdf.name}:{latest_pdf.stat().st_size}"
        if pdf_key in imported:
            return False  # 既に処理済み

        # 画像切り出し
        logger.info(f"[NabCostPrice] New PDF found: {latest_pdf.name}, extracting charts...")
        success = self._extract_charts_from_pdf(latest_pdf)
        if success:
            self._mark_pdf_as_imported(latest_pdf)

            # メタデータをRedisに保存
            now = datetime.now(JST)
            redis_client.set(self.CACHE_KEY, {
                "last_updated": now.isoformat(),
                "pdf_name": latest_pdf.name,
                "cost_growth_exists": (CACHE_DIR / SCREENSHOTS["cost_growth"]["filename"]).exists(),
                "output_price_growth_exists": (CACHE_DIR / SCREENSHOTS["output_price_growth"]["filename"]).exists(),
            }, expire=0)

        return success

    def get_screenshot_urls(self) -> Dict[str, Any]:
        """スクリーンショットURL一覧を取得"""
        # 未処理PDFがあれば自動処理
        self.check_and_extract()

        result = {
            "screenshots": [],
            "last_updated": None,
            "next_release": self._get_next_release(),
        }

        for key, config in SCREENSHOTS.items():
            screenshot_path = CACHE_DIR / config["filename"]
            result["screenshots"].append({
                "key": key,
                "label": config["label"],
                "label_ja": config["label_ja"],
                "url": f"/cache/australia/inflation/{config['filename']}" if screenshot_path.exists() else None,
                "exists": screenshot_path.exists(),
            })

        cached_meta = redis_client.get(self.CACHE_KEY)
        if cached_meta:
            result["last_updated"] = cached_meta.get("last_updated")
            result["pdf_name"] = cached_meta.get("pdf_name")
        else:
            # ファイルの更新日時を使用
            for config in SCREENSHOTS.values():
                p = CACHE_DIR / config["filename"]
                if p.exists():
                    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=JST)
                    result["last_updated"] = mtime.isoformat()
                    break

        return result

    def get_screenshot_path(self, key: str) -> Optional[Path]:
        """指定キーのスクリーンショットパスを取得"""
        config = SCREENSHOTS.get(key)
        if not config:
            return None
        path = CACHE_DIR / config["filename"]
        return path if path.exists() else None

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            logger.error(f"[NabCostPrice] Error getting next release: {e}")
            return None

    def _load_imported_pdfs(self) -> set:
        """処理済みPDFリストを読み込む"""
        try:
            import json
            if IMPORTED_PDF_FILE.exists():
                with open(IMPORTED_PDF_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get("imported", []))
        except Exception as e:
            logger.error(f"[NabCostPrice] Error loading imported PDFs list: {e}")
        return set()

    def _mark_pdf_as_imported(self, pdf_path: Path) -> None:
        """PDFを処理済みとしてマーク"""
        try:
            import json
            imported = self._load_imported_pdfs()
            pdf_key = f"{pdf_path.name}:{pdf_path.stat().st_size}"
            imported.add(pdf_key)

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(IMPORTED_PDF_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "imported": list(imported),
                    "last_updated": datetime.now(JST).isoformat()
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"[NabCostPrice] Marked PDF as imported: {pdf_path.name}")
        except Exception as e:
            logger.error(f"[NabCostPrice] Error marking PDF as imported: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化（画像も削除）"""
        redis_client.delete(self.CACHE_KEY)
        # 処理済みPDFリストも削除（次回再抽出させる）
        if IMPORTED_PDF_FILE.exists():
            IMPORTED_PDF_FILE.unlink()
        return True

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        cached_meta = redis_client.get(self.CACHE_KEY)
        latest_pdf = self._find_latest_pdf()

        return {
            "indicator": "NAB Business Survey - Cost & Price Charts",
            "source": "NAB Monthly Business Survey (PDF)",
            "cache_key": self.CACHE_KEY,
            "last_updated": cached_meta.get("last_updated") if cached_meta else None,
            "pdf_name": cached_meta.get("pdf_name") if cached_meta else None,
            "latest_pdf_found": latest_pdf.name if latest_pdf else None,
            "cost_growth_exists": (CACHE_DIR / SCREENSHOTS["cost_growth"]["filename"]).exists(),
            "output_price_growth_exists": (CACHE_DIR / SCREENSHOTS["output_price_growth"]["filename"]).exists(),
            "next_release": self._get_next_release(),
        }


# シングルトンインスタンス
nab_business_survey_cost_price_service = NabBusinessSurveyCostPriceService()

# パス参照用
SCREENSHOT_PATHS = {
    key: CACHE_DIR / config["filename"] for key, config in SCREENSHOTS.items()
}
