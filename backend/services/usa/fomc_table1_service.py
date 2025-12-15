#!/usr/bin/env python3
"""
FOMC Economic Projections Table 1処理サービス
FOMCのProjections PDFからTable 1を画像として抽出
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


class FOMCTable1Service:
    """FOMC Economic Projections Table 1から表を抽出するサービス"""

    BASE_URL = "https://www.federalreserve.gov/monetarypolicy/files/fomcprojtabl{date}.pdf"
    CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "fomc_table1"

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

    def extract_table_1(self, pdf_url: str) -> Optional[bytes]:
        """
        PDFからTable 1を画像として抽出
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

            # Table 1は通常2ページ目 (インデックス1) にある
            table_1_image = None

            # PDFが2ページ以上あるか確認
            if len(doc) < 2:
                print(f"Warning: PDF has only {len(doc)} pages, expected at least 2")
                doc.close()
                return None

            # 2ページ目 (インデックス1) を取得
            page = doc[1]  # 0-indexed: ページ2 = インデックス1
            print(f"Extracting Table 1 from page 2 (index 1)")
            print(f"  Page size: {page.rect.width} x {page.rect.height}, rotation: {page.rotation}")

            # Table 1の位置を検出
            text_instances = page.search_for("Table 1")

            # デフォルトのクロップ開始位置（上端からの割合）
            crop_top_ratio = 0.0  # デフォルトは0%から（ページ全体を使用）

            if text_instances:
                # Table 1のテキストが見つかった場合、その位置を基準にする
                first_instance = text_instances[0]  # fitz.Rect オブジェクト

                # ページが90度回転している場合、座標系を調整
                if page.rotation == 90:
                    # 回転後の実際のページサイズを取得
                    page_width = page.rect.width  # 792
                    page_height = page.rect.height  # 612

                    # Table 1の位置（回転座標系）
                    table_left = first_instance.x0

                    # 左端からの割合を計算
                    crop_top_ratio = max(0, (table_left / page_width) - 0.05)  # 5%左から開始

                    print(f"  Table 1 found at x={table_left:.1f} (page width={page_width:.1f}, rotated)")
                    print(f"  Crop left ratio: {crop_top_ratio:.3f}")
                else:
                    # 通常の縦向きページの場合
                    page_height = page.rect.height
                    table_top = first_instance.y0
                    crop_top_ratio = max(0, (table_top / page_height) - 0.02)

                    print(f"  Table 1 found at y={table_top:.1f} (page height={page_height:.1f})")
                    print(f"  Crop top ratio: {crop_top_ratio:.3f}")
            else:
                print(f"  Warning: 'Table 1' text not found, using default crop")

            # ページ全体を画像として取得 (高解像度、回転を正しく処理)
            mat = fitz.Matrix(3.0, 3.0)  # 3倍の解像度
            pix = page.get_pixmap(matrix=mat)

            # PILイメージに変換
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Table 1の領域をクロップ
            width, height = img.size

            # ページが90度回転している場合、横向きのクロップになる
            if page.rotation == 90:
                # 横向きページ: 左から右にクロップ（横幅を広めに取得）
                crop_box = (
                    int(width * crop_top_ratio),           # 左端からTable 1の位置
                    int(height * 0.05),                    # 上端から5%
                    int(width * (crop_top_ratio + 0.85)),  # Table 1から右に85%（横幅を広く）
                    int(height * 0.95)                     # 下端まで95%
                )
            else:
                # 縦向きページ: Table 1は縦に長いテーブルなので、下部まで広めに取得
                crop_box = (
                    int(width * 0.1),                       # 左端から10%
                    int(height * crop_top_ratio),           # Table 1の位置に基づいて動的に調整
                    int(width * 0.9),                       # 右端まで90%
                    int(height * (crop_top_ratio + 0.70))   # Table 1から下に70%の高さ
                )

            cropped_image = img.crop(crop_box)

            # 90%に縮小
            new_width = int(cropped_image.width * 0.9)
            new_height = int(cropped_image.height * 0.9)
            table_1_image = cropped_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            doc.close()

            if table_1_image is None:
                return None

            # PNG形式でバイト列に変換
            img_byte_arr = io.BytesIO()
            table_1_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            return img_byte_arr.getvalue()

        except Exception as e:
            print(f"Error extracting Table 1: {e}")
            raise

    def save_table_1(self, date: datetime, image_data: bytes) -> str:
        """
        Table 1の画像をキャッシュに保存
        Args:
            date: FOMC発表日
            image_data: 画像データ
        Returns:
            保存したファイルのパス
        """
        date_str = date.strftime("%Y%m%d")
        file_path = self.CACHE_DIR / f"table1_{date_str}.png"

        with open(file_path, 'wb') as f:
            f.write(image_data)

        # メタデータも保存
        metadata = {
            "date": date.isoformat(),
            "url": self.get_pdf_url(date),
            "updated_at": datetime.utcnow().isoformat()
        }

        metadata_path = self.CACHE_DIR / f"table1_{date_str}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        return str(file_path)

    def get_cached_table_1(self, date: datetime) -> Optional[bytes]:
        """
        キャッシュからTable 1を取得
        Args:
            date: FOMC発表日
        Returns:
            画像データ (存在しない場合はNone)
        """
        date_str = date.strftime("%Y%m%d")
        file_path = self.CACHE_DIR / f"table1_{date_str}.png"

        if file_path.exists():
            with open(file_path, 'rb') as f:
                return f.read()

        return None

    def update_table_1(self, date: datetime) -> Dict:
        """
        Table 1を更新 (PDFから抽出してキャッシュに保存)
        Args:
            date: FOMC発表日
        Returns:
            結果の辞書
        """
        try:
            pdf_url = self.get_pdf_url(date)
            image_data = self.extract_table_1(pdf_url)

            if image_data is None:
                return {
                    "success": False,
                    "error": "Table 1 not found in PDF"
                }

            file_path = self.save_table_1(date, image_data)

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

    def get_latest_table_1(self) -> Optional[bytes]:
        """
        最新のTable 1を取得
        Returns:
            画像データ (存在しない場合はNone)
        """
        # キャッシュディレクトリから最新のファイルを探す
        png_files = sorted(self.CACHE_DIR.glob("table1_*.png"), reverse=True)

        if png_files:
            with open(png_files[0], 'rb') as f:
                return f.read()

        return None

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
        for file_path in self.CACHE_DIR.glob("table1_*"):
            try:
                # ファイル名から日付を抽出
                filename = file_path.stem
                if "_metadata" in filename:
                    date_str = filename.replace("table1_", "").replace("_metadata", "")
                else:
                    date_str = filename.replace("table1_", "")

                file_date = datetime.strptime(date_str, "%Y%m%d")

                # カットオフ日より古い場合は削除
                if file_date < cutoff_date:
                    file_path.unlink()
                    deleted_count += 1
                    print(f"Deleted old cache: {file_path}")

            except Exception as e:
                print(f"Error processing file {file_path}: {e}")

        return deleted_count
