"""
Dukascopyサービスの動作テストスクリプト

使用方法:
    cd backend
    pip install dukascopy-python
    python scripts/test_dukascopy.py
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

UTC = ZoneInfo("UTC")


def test_dukascopy_availability():
    """dukascopy-pythonが利用可能かテスト"""
    print("=" * 60)
    print("1. dukascopy-python 利用可能性テスト")
    print("=" * 60)

    try:
        import dukascopy_python
        print(f"✓ dukascopy-python インポート成功")
        print(f"  バージョン情報: {dukascopy_python.__version__ if hasattr(dukascopy_python, '__version__') else 'unknown'}")
        return True
    except ImportError as e:
        print(f"✗ dukascopy-python インポート失敗: {e}")
        print("  インストールコマンド: pip install dukascopy-python")
        return False


def test_instrument_lookup():
    """Instrument検索テスト"""
    print("\n" + "=" * 60)
    print("2. Instrument 検索テスト")
    print("=" * 60)

    try:
        from dukascopy_python.instruments import get_instrument_by_symbol

        test_symbols = ["USDJPY", "EURUSD", "XAUUSD", "USA500IDXUSD"]

        for symbol in test_symbols:
            instrument = get_instrument_by_symbol(symbol)
            if instrument:
                print(f"✓ {symbol}: {instrument}")
            else:
                print(f"✗ {symbol}: Not found")

        return True
    except Exception as e:
        print(f"✗ Instrument検索エラー: {e}")
        return False


def test_fetch_sample_data():
    """サンプルデータ取得テスト"""
    print("\n" + "=" * 60)
    print("3. サンプルデータ取得テスト")
    print("=" * 60)

    try:
        import dukascopy_python
        from dukascopy_python.instruments import get_instrument_by_symbol

        # USDJPY の直近1時間のデータを取得
        instrument = get_instrument_by_symbol("USDJPY")
        if not instrument:
            print("✗ USDJPY instrument not found")
            return False

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=1)

        print(f"  取得範囲: {start_time} ~ {end_time}")
        print(f"  Instrument: {instrument}")

        df = dukascopy_python.fetch(
            instrument=instrument,
            interval=dukascopy_python.INTERVAL_MIN_1,
            offer_side=dukascopy_python.OFFER_SIDE_BID,
            start=start_time,
            end=end_time,
        )

        if df is None or df.empty:
            print("✗ データが取得できませんでした（市場がクローズしている可能性）")
            return False

        print(f"✓ {len(df)} 件のデータを取得")
        print("\n  最初の5件:")
        print(df.head().to_string())
        print("\n  最後の5件:")
        print(df.tail().to_string())

        return True

    except Exception as e:
        print(f"✗ データ取得エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dukascopy_service():
    """DukascopyServiceクラスのテスト"""
    print("\n" + "=" * 60)
    print("4. DukascopyService クラステスト")
    print("=" * 60)

    try:
        from services.market.dukascopy_service import dukascopy_service

        # サポート銘柄確認
        symbols = dukascopy_service.get_supported_symbols()
        print(f"✓ サポート銘柄: {len(symbols)} 件")
        print(f"  {symbols[:5]}...")

        # 銘柄マッピング確認
        for symbol_id in ["usdjpy", "gold", "sp500"]:
            duka = dukascopy_service.get_dukascopy_symbol(symbol_id)
            print(f"  {symbol_id} → {duka}")

        return True

    except Exception as e:
        print(f"✗ DukascopyServiceエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fetch_around_release():
    """指標発表時刻前後のデータ取得テスト"""
    print("\n" + "=" * 60)
    print("5. 指標発表時刻前後データ取得テスト")
    print("=" * 60)

    try:
        from services.market.dukascopy_service import dukascopy_service

        # 仮の発表時刻（1週間前の正午UTC）
        release_time = datetime.now(UTC).replace(
            hour=12, minute=0, second=0, microsecond=0
        ) - timedelta(days=7)

        print(f"  発表時刻: {release_time}")
        print(f"  銘柄: usdjpy")
        print(f"  取得範囲: ±30分（テスト用に短縮）")

        result = dukascopy_service.fetch_around_release_time(
            symbol_id="usdjpy",
            release_time=release_time,
            before_minutes=30,
            after_minutes=30,
            interval="1m"
        )

        print(f"\n✓ 取得結果:")
        print(f"  データ件数: {result['metadata']['data_count']}")

        if result['data']:
            print(f"\n  最初のデータ:")
            print(f"    {result['data'][0]}")
            print(f"  最後のデータ:")
            print(f"    {result['data'][-1]}")

        return True

    except Exception as e:
        print(f"✗ 発表時刻データ取得エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト実行"""
    print("\n" + "=" * 60)
    print("Dukascopy サービス 動作テスト")
    print("=" * 60 + "\n")

    results = {
        "利用可能性": test_dukascopy_availability(),
        "Instrument検索": test_instrument_lookup(),
        "サンプルデータ取得": test_fetch_sample_data(),
        "DukascopyService": test_dukascopy_service(),
        "発表時刻データ取得": test_fetch_around_release(),
    }

    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("全テスト成功！")
    else:
        print("一部テストが失敗しました。エラーログを確認してください。")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
