"""
UK住宅価格指数PDFインポートスクリプト

手動ダウンロードしたPDFからHalifax/Rightmoveの住宅価格指数をDBにインポート

使用方法:
    python scripts/import_uk_housing_pdf.py                    # 全て
    python scripts/import_uk_housing_pdf.py --halifax          # Halifaxのみ
    python scripts/import_uk_housing_pdf.py --rightmove        # Rightmoveのみ
    python scripts/import_uk_housing_pdf.py --dry-run          # 実行せずに確認

PDFファイル配置:
    Halifax:   backend/data/pdf/uk/YYYYMM-halifax-house-price-index.pdf
    Rightmove: backend/data/pdf/uk/Rightmove-HPI-YYYYMMl.pdf
"""
import sys
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))


def import_halifax(dry_run: bool = False) -> bool:
    """Halifaxデータをインポート"""
    from services.uk.halifax_house_price_service import halifax_house_price_service

    print("\n=== Halifax House Price Index ===")

    # PDFからデータを読み込み
    pdf_data = halifax_house_price_service._load_latest_from_pdf()

    if not pdf_data:
        print("❌ Halifax: PDFからデータを取得できませんでした")
        print("   PDFファイルを backend/data/pdf/uk/ に配置してください")
        print("   ファイル名形式: YYYYMM-halifax-house-price-index.pdf")
        return False

    mom = pdf_data.get("mom")
    yoy = pdf_data.get("yoy")

    print(f"📄 PDFから取得:")
    if mom:
        print(f"   MoM: {mom['date']} = {mom['value']}%")
    if yoy:
        print(f"   YoY: {yoy['date']} = {yoy['value']}%")

    if dry_run:
        print("🔍 [DRY-RUN] DBへの保存はスキップします")
        return True

    # DBに保存
    success = halifax_house_price_service._save_pdf_data_to_db(pdf_data)
    if success:
        print("✅ Halifax: DBに保存しました")
        # キャッシュをクリア
        halifax_house_price_service.invalidate_cache()
        print("   キャッシュをクリアしました")
    else:
        print("❌ Halifax: DBへの保存に失敗しました")

    return success


def import_rightmove(dry_run: bool = False) -> bool:
    """Rightmoveデータをインポート"""
    from services.uk.rightmove_house_price_service import rightmove_house_price_service

    print("\n=== Rightmove House Price Index ===")

    # PDFからデータを読み込み
    pdf_data = rightmove_house_price_service._load_latest_from_pdf()

    if not pdf_data:
        print("❌ Rightmove: PDFからデータを取得できませんでした")
        print("   PDFファイルを backend/data/pdf/uk/ に配置してください")
        print("   ファイル名形式: Rightmove-HPI-YYYYMMl.pdf")
        return False

    mom = pdf_data.get("mom")
    yoy = pdf_data.get("yoy")

    print(f"📄 PDFから取得:")
    if mom:
        print(f"   MoM: {mom['date']} = {mom['value']}%")
    if yoy:
        print(f"   YoY: {yoy['date']} = {yoy['value']}%")

    if dry_run:
        print("🔍 [DRY-RUN] DBへの保存はスキップします")
        return True

    # DBに保存
    success = rightmove_house_price_service._save_pdf_data_to_db(pdf_data)
    if success:
        print("✅ Rightmove: DBに保存しました")
        # キャッシュをクリア
        rightmove_house_price_service.invalidate_cache()
        print("   キャッシュをクリアしました")
    else:
        print("❌ Rightmove: DBへの保存に失敗しました")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="UK住宅価格指数PDFインポート",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
PDFファイル配置場所:
  backend/data/pdf/uk/

ファイル名形式:
  Halifax:   YYYYMM-halifax-house-price-index.pdf (例: 202512-halifax-house-price-index.pdf)
  Rightmove: Rightmove-HPI-YYYYMMl.pdf (例: Rightmove-HPI-202601l.pdf)
        """
    )
    parser.add_argument("--halifax", action="store_true", help="Halifaxのみインポート")
    parser.add_argument("--rightmove", action="store_true", help="Rightmoveのみインポート")
    parser.add_argument("--dry-run", action="store_true", help="実行せずに確認のみ")

    args = parser.parse_args()

    # どちらも指定されていなければ両方
    if not args.halifax and not args.rightmove:
        args.halifax = True
        args.rightmove = True

    print("=" * 50)
    print("UK住宅価格指数 PDFインポート")
    print("=" * 50)

    if args.dry_run:
        print("🔍 DRY-RUN モード（DBへの保存は行いません）")

    results = []

    if args.halifax:
        results.append(("Halifax", import_halifax(args.dry_run)))

    if args.rightmove:
        results.append(("Rightmove", import_rightmove(args.dry_run)))

    print("\n" + "=" * 50)
    print("結果サマリー:")
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"  {name}: {status}")
    print("=" * 50)


if __name__ == "__main__":
    main()
