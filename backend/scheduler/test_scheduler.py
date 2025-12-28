#!/usr/bin/env python3
"""
スケジューラーのテストスクリプト

使用方法:
    cd backend
    python -m scheduler.test_scheduler
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def test_indicator_registry():
    """指標レジストリのテスト"""
    print("=" * 60)
    print("Testing Indicator Registry")
    print("=" * 60)

    try:
        from backend.scheduler.indicator_registry import (
            get_enabled_indicators,
            get_indicator_summary,
            Category
        )
    except ImportError:
        from scheduler.indicator_registry import (
            get_enabled_indicators,
            get_indicator_summary,
            Category
        )

    enabled = get_enabled_indicators()
    print(f"\nTotal enabled indicators: {len(enabled)}")

    summary = get_indicator_summary()
    print("\nBy category:")
    for cat, info in summary["by_category"].items():
        print(f"  {cat}: {info['count']} indicators")

    print("\nBy schedule checker:")
    for checker, indicators in summary["by_schedule_checker"].items():
        print(f"  {checker}: {len(indicators)} indicators")
        for ind in indicators[:3]:
            print(f"    - {ind}")
        if len(indicators) > 3:
            print(f"    ... and {len(indicators) - 3} more")

    return True


def test_schedule_checkers():
    """スケジュールチェッカーのテスト"""
    print("\n" + "=" * 60)
    print("Testing Schedule Checkers")
    print("=" * 60)

    try:
        from backend.services.usa.release_schedule_utils import (
            UNEMPLOYMENT_RATE_CHECKER,
            RETAIL_SALES_CHECKER,
            WEEKLY_CLAIMS_CHECKER,
            NER_PULSE_CHECKER,
            ATLANTA_FED_WAGE_CHECKER,
            INDEED_WAGE_CHECKER,
            ISM_MANUFACTURING_CHECKER,
            CB_CONSUMER_CONFIDENCE_CHECKER,
        )
    except ImportError:
        from services.usa.release_schedule_utils import (
            UNEMPLOYMENT_RATE_CHECKER,
            RETAIL_SALES_CHECKER,
            WEEKLY_CLAIMS_CHECKER,
            NER_PULSE_CHECKER,
            ATLANTA_FED_WAGE_CHECKER,
            INDEED_WAGE_CHECKER,
            ISM_MANUFACTURING_CHECKER,
            CB_CONSUMER_CONFIDENCE_CHECKER,
        )

    checkers = [
        ("UNEMPLOYMENT_RATE_CHECKER", UNEMPLOYMENT_RATE_CHECKER),
        ("RETAIL_SALES_CHECKER", RETAIL_SALES_CHECKER),
        ("WEEKLY_CLAIMS_CHECKER", WEEKLY_CLAIMS_CHECKER),
        ("ISM_MANUFACTURING_CHECKER", ISM_MANUFACTURING_CHECKER),
        ("CB_CONSUMER_CONFIDENCE_CHECKER", CB_CONSUMER_CONFIDENCE_CHECKER),
        ("NER_PULSE_CHECKER", NER_PULSE_CHECKER),
        ("ATLANTA_FED_WAGE_CHECKER", ATLANTA_FED_WAGE_CHECKER),
        ("INDEED_WAGE_CHECKER", INDEED_WAGE_CHECKER),
    ]

    now = datetime.now(JST)
    print(f"\nCurrent time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    for name, checker in checkers:
        try:
            status = checker.get_status()
            pattern = status.get("pattern", "unknown")
            next_release = status.get("next_release") or status.get("this_month_release")

            print(f"\n{name}:")
            print(f"  Pattern: {pattern}")
            if next_release:
                print(f"  Next release: {next_release}")
            if status.get("in_release_period") is not None:
                print(f"  In release period: {status['in_release_period']}")
            if status.get("release_days"):
                print(f"  Release days: {status['release_days']}")

        except Exception as e:
            print(f"\n{name}: Error - {e}")

    print("")  # Extra newline

    return True


def test_scheduler_initialization():
    """スケジューラー初期化のテスト"""
    print("\n" + "=" * 60)
    print("Testing Scheduler Initialization")
    print("=" * 60)

    try:
        from backend.scheduler.indicator_scheduler import IndicatorScheduler
    except ImportError:
        from scheduler.indicator_scheduler import IndicatorScheduler

    scheduler = IndicatorScheduler()
    print("\nScheduler created successfully")

    # スケジュールチェッカーのインポートテスト
    print("\nTesting schedule checker imports...")
    checker = scheduler._get_schedule_checker("UNEMPLOYMENT_RATE_CHECKER")
    if checker:
        print("  [OK] UNEMPLOYMENT_RATE_CHECKER imported")
    else:
        print("  [NG] UNEMPLOYMENT_RATE_CHECKER failed")

    checker = scheduler._get_schedule_checker("WEEKLY_CLAIMS_CHECKER")
    if checker:
        print("  [OK] WEEKLY_CLAIMS_CHECKER imported")
    else:
        print("  [NG] WEEKLY_CLAIMS_CHECKER failed")

    # サービスインスタンスのインポートテスト
    print("\nTesting service imports...")

    try:
        from backend.scheduler.indicator_registry import get_enabled_indicators
    except ImportError:
        from scheduler.indicator_registry import get_enabled_indicators

    indicators = get_enabled_indicators()
    success_count = 0
    fail_count = 0

    for config in indicators[:5]:  # 最初の5つだけテスト
        service = scheduler._get_service_instance(config)
        if service:
            print(f"  [OK] {config.name_en}")
            success_count += 1
        else:
            print(f"  [NG] {config.name_en}")
            fail_count += 1

    print(f"\nService import results: {success_count} success, {fail_count} failed")

    return True


def test_next_release_calculation():
    """次回発表時刻計算のテスト"""
    print("\n" + "=" * 60)
    print("Testing Next Release Time Calculation")
    print("=" * 60)

    try:
        from backend.scheduler.indicator_scheduler import IndicatorScheduler
    except ImportError:
        from scheduler.indicator_scheduler import IndicatorScheduler

    scheduler = IndicatorScheduler()

    checkers_to_test = [
        "WEEKLY_CLAIMS_CHECKER",
        "UNEMPLOYMENT_RATE_CHECKER",
        "RETAIL_SALES_CHECKER",
        "NER_PULSE_CHECKER",
        "ISM_MANUFACTURING_CHECKER",
    ]

    now = datetime.now(JST)
    print(f"\nCurrent time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    for checker_name in checkers_to_test:
        checker = scheduler._get_schedule_checker(checker_name)
        if checker:
            next_release = scheduler._get_next_release_time(checker)
            if next_release:
                print(f"\n{checker_name}:")
                print(f"  Next release: {next_release.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            else:
                print(f"\n{checker_name}: No upcoming release found")
        else:
            print(f"\n{checker_name}: Checker not found")

    return True


def main():
    """メインテスト実行"""
    print("\n" + "=" * 60)
    print("Economic Indicator Scheduler - Test Suite")
    print("=" * 60)

    tests = [
        ("Indicator Registry", test_indicator_registry),
        ("Schedule Checkers", test_schedule_checkers),
        ("Scheduler Initialization", test_scheduler_initialization),
        ("Next Release Calculation", test_next_release_calculation),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            results.append((name, False, str(e)))
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for name, success, error in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {name}")
        if error:
            print(f"       Error: {error}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("All tests passed!" if all_passed else "Some tests failed."))

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
