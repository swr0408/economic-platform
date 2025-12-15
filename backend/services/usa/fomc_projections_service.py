#!/usr/bin/env python3
"""
FOMC Projections PDF処理サービス
FOMCのProjections PDFからFigure 2（ドットプロット）を画像として抽出
"""

import requests
import io
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path
import json

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class FOMCProjectionsService:
    """FOMC Projections PDFから図を抽出するサービス"""

    BASE_URL = "https://www.federalreserve.gov/monetarypolicy/files/fomcprojtabl{date}.pdf"
    CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "fomc_projections"

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_pdf_url(self, date: datetime) -> str:
        """
        指定された日付のFOMC Projections PDFのURLを生成
        Args:
            date: FOMC発表日 (アメリカ時間)
        Returns:
            PDFのURL
        """
        date_str = date.strftime("%Y%m%d")
        return self.BASE_URL.format(date=date_str)

    def extract_figure_2(self, pdf_url: str) -> Optional[bytes]:
        """
        PDFからFigure 2を画像として抽出
        Args:
            pdf_url: PDFのURL
        Returns:
            画像データ (PNG形式のバイト列)
        """
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF (fitz) がインストールされていません")

        if not HAS_PIL:
            raise ImportError("Pillow (PIL) がインストールされていません")

        try:
            # PDFをダウンロード
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()

            pdf_content = io.BytesIO(response.content)

            # PDFを開く
            doc = fitz.open(stream=pdf_content, filetype="pdf")

            # Dot Plot (Figure 2) は通常4ページ目 (インデックス3) にある
            figure_2_image = None

            # PDFが4ページ以上あるか確認
            if len(doc) < 4:
                print(f"Warning: PDF has only {len(doc)} pages, expected at least 4")
                doc.close()
                return None

            # 4ページ目 (インデックス3) を取得
            page = doc[3]  # 0-indexed: ページ4 = インデックス3
            print(f"Extracting Figure 2 from page 4 (index 3)")

            # Figure 2の位置を検出
            text_instances = page.search_for("Figure 2")

            # デフォルトのクロップ開始位置（上端からの割合）
            crop_top_ratio = 0.0

            if text_instances:
                # Figure 2のテキストが見つかった場合、その位置を基準にする
                first_instance = text_instances[0]  # fitz.Rect オブジェクト
                page_height = page.rect.height

                # Figure 2の上端位置（ページ上端からのピクセル数）
                figure_top = first_instance.y0

                # ページ高さに対する割合を計算
                crop_top_ratio = max(0, (figure_top / page_height) - 0.02)  # 2%上から開始

                print(f"  Figure 2 found at y={figure_top:.1f} (page height={page_height:.1f})")
                print(f"  Crop top ratio: {crop_top_ratio:.3f}")
            else:
                print(f"  Warning: 'Figure 2' text not found, using default crop")

            # ページ全体を画像として取得 (高解像度)
            mat = fitz.Matrix(3.0, 3.0)  # 3倍の解像度
            pix = page.get_pixmap(matrix=mat)

            # PILイメージに変換
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Figure 2の領域をクロップ
            width, height = img.size

            crop_box = (
                int(width * 0.1),                       # 左端から10%
                int(height * crop_top_ratio),           # Figure 2の位置に基づいて動的に調整
                int(width * 0.9),                       # 右端まで90%
                int(height * (crop_top_ratio + 0.6))   # Figure 2から下に60%の高さ
            )

            cropped_image = img.crop(crop_box)

            # 90%に縮小
            new_width = int(cropped_image.width * 0.9)
            new_height = int(cropped_image.height * 0.9)
            figure_2_image = cropped_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            doc.close()

            if figure_2_image is None:
                return None

            # PNG形式でバイト列に変換
            img_byte_arr = io.BytesIO()
            figure_2_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            return img_byte_arr.getvalue()

        except Exception as e:
            print(f"Error extracting Figure 2: {e}")
            raise

    def save_figure_2(self, date: datetime, image_data: bytes) -> str:
        """
        Figure 2の画像をキャッシュに保存
        Args:
            date: FOMC発表日
            image_data: 画像データ
        Returns:
            保存したファイルのパス
        """
        date_str = date.strftime("%Y%m%d")
        file_path = self.CACHE_DIR / f"figure2_{date_str}.png"

        with open(file_path, 'wb') as f:
            f.write(image_data)

        # メタデータも保存
        metadata = {
            "date": date.isoformat(),
            "url": self.get_pdf_url(date),
            "updated_at": datetime.utcnow().isoformat()
        }

        metadata_path = self.CACHE_DIR / f"figure2_{date_str}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        return str(file_path)

    def get_cached_figure_2(self, date: datetime) -> Optional[bytes]:
        """
        キャッシュからFigure 2を取得
        Args:
            date: FOMC発表日
        Returns:
            画像データ (存在しない場合はNone)
        """
        date_str = date.strftime("%Y%m%d")
        file_path = self.CACHE_DIR / f"figure2_{date_str}.png"

        if file_path.exists():
            with open(file_path, 'rb') as f:
                return f.read()

        return None

    def update_figure_2(self, date: datetime) -> Dict:
        """
        Figure 2を更新 (PDFから抽出してキャッシュに保存)
        Args:
            date: FOMC発表日
        Returns:
            結果の辞書
        """
        try:
            pdf_url = self.get_pdf_url(date)
            image_data = self.extract_figure_2(pdf_url)

            if image_data is None:
                return {
                    "success": False,
                    "error": "Figure 2 not found in PDF"
                }

            file_path = self.save_figure_2(date, image_data)

            return {
                "success": True,
                "file_path": file_path,
                "date": date.isoformat(),
                "url": pdf_url
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_or_update_figure_2(self, date: datetime) -> bytes:
        """
        Figure 2を取得 (キャッシュがなければPDFから抽出)
        Args:
            date: FOMC発表日
        Returns:
            画像データ
        """
        # まずキャッシュを確認
        cached_data = self.get_cached_figure_2(date)
        if cached_data:
            return cached_data

        # キャッシュがなければPDFから抽出
        result = self.update_figure_2(date)

        if not result["success"]:
            raise Exception(result.get("error", "Unknown error"))

        return self.get_cached_figure_2(date)

    def clean_old_cache(self, keep_days: int = 365) -> int:
        """
        古いキャッシュを削除 (指定日数より古いファイル)
        Args:
            keep_days: 保持する日数 (デフォルト: 365日)
        Returns:
            削除したファイル数
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0

        # キャッシュディレクトリ内の全ファイルを確認
        for file_path in self.CACHE_DIR.glob("figure2_*"):
            try:
                # ファイル名から日付を抽出 (figure2_YYYYMMDD.png or figure2_YYYYMMDD_metadata.json)
                filename = file_path.stem
                if "_metadata" in filename:
                    date_str = filename.replace("figure2_", "").replace("_metadata", "")
                else:
                    date_str = filename.replace("figure2_", "")

                file_date = datetime.strptime(date_str, "%Y%m%d")

                # カットオフ日より古い場合は削除
                if file_date < cutoff_date:
                    file_path.unlink()
                    deleted_count += 1
                    print(f"Deleted old cache: {file_path}")

            except Exception as e:
                print(f"Error processing file {file_path}: {e}")

        return deleted_count
