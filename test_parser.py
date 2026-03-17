"""
パーサーのユニットテスト v2
============================
MOTIE報道資料の実際のテキストパターンでパーサーの正確性を検証する。
診断結果から得た実データパターンを含む。
"""

import sys
sys.path.insert(0, ".")

from scraper import (
    parse_trade_report_ko,
    parse_ict_report_text,
    _parse_month_headers,
    deduplicate_records,
    SemiconductorExportRecord,
)


def test_parse_trade_ko_pattern1():
    """수출입 동향: 반도체 수출은 XXX억 달러(+XX.X%) パターン"""
    text = """
    2025년 3월 수출입 동향
    
    □ (반도체) 반도체 수출은 AI 서버용 HBM 수요 확대 등에 힘입어 
    131억 달러(+11.9%)를 기록하며 전년 동월 대비 증가
    """
    records = parse_trade_report_ko(text)
    assert len(records) == 1, f"Expected 1 record, got {len(records)}"
    r = records[0]
    assert r.ref_month == "2025-03"
    assert r.value_usd_billion == 13.1
    assert r.yoy_pct == 11.9
    print("✓ test_parse_trade_ko_pattern1")


def test_parse_trade_ko_pattern2():
    """수출입 동향: 반도체(XXX억 달러, XX.X%↑) パターン"""
    text = """
    2026년 2월 수출입 동향
    
    □ 15대 품목 중 반도체(252억 달러, 160.9%↑), 컴퓨터(222%↑), 
    선박(41%↑) 등이 증가
    """
    records = parse_trade_report_ko(text)
    assert len(records) == 1, f"Expected 1 record, got {len(records)}"
    r = records[0]
    assert r.ref_month == "2026-02"
    assert r.value_usd_billion == 25.2
    assert r.yoy_pct == 160.9
    print("✓ test_parse_trade_ko_pattern2")


def test_parse_trade_ko_negative():
    """수출입 동향: △（マイナス）パターン"""
    text = """
    2023년 5월 수출입 동향
    
    반도체 수출은 72억 달러(△36.2%)로 감소
    """
    records = parse_trade_report_ko(text)
    assert len(records) == 1
    assert records[0].value_usd_billion == 7.2
    assert records[0].yoy_pct == -36.2
    print("✓ test_parse_trade_ko_negative")


def test_parse_ict_inline_trend_real():
    """
    ICT レポート: 診断結果から得た実データのインライン推移パターン。
    ASCII引用符 ' (U+0027) のケース。
    """
    text = """
    2026년 2월 정보통신산업(ICT) 수출입 동향
    
    ○ (반도체 : 251.7억 달러, 160.8%↑) 글로벌 AI 서버 수요 확대로 메모리 반도체 
    고정가격 오름세 와 고부가제품 수출 확대로 3개월 연속 200억 달러 상회 기록
    
    ** 반도체 수출 역대 순위(억 달러) : (1위) 251.7('26.2월) → (2위) 207.7('25.12월)
    
    ※ 반도체 수출 추이(억 달러, %) : ('25.11월)172.7(38.6↑) → ('25.12월)207.7(43.2↑) → ('26.1월)205.5(102.7↑) → ('26.2월)251.7(160.8↑)
    
    • 중소·중견기업(47.0억 달러, 1.5%↑)
    """
    records = parse_ict_report_text(text)
    assert len(records) >= 4, f"Expected >=4 records, got {len(records)}"
    by_month = {r.ref_month: r for r in records}
    assert by_month["2025-11"].value_usd_billion == 17.27
    assert by_month["2026-02"].value_usd_billion == 25.17
    assert by_month["2026-02"].yoy_pct == 160.8
    print("✓ test_parse_ict_inline_trend_real")
    for r in records:
        print(f"  {r.ref_month}: ${r.value_usd_billion}B (YoY {r.yoy_pct}%)")


def test_parse_ict_inline_trend_unicode_quotes():
    """
    ICTレポート: Unicode引用符 \u2018 \u2019 のケース（MOTIE実サイトで使われる）。
    """
    text = (
        "2026년 2월 정보통신산업(ICT) 수출입 동향\n"
        "\n"
        "※ 반도체 수출 추이(억 달러, %) : "
        "(\u201825.11월)172.7(38.6↑) → (\u201825.12월)207.7(43.2↑) → "
        "(\u201826.1월)205.5(102.7↑) → (\u201826.2월)251.7(160.8↑)\n"
        "\n"
        "• 다음 섹션"
    )
    records = parse_ict_report_text(text)
    assert len(records) >= 4, f"Expected >=4 records, got {len(records)}: unicode quotes"
    by_month = {r.ref_month: r for r in records}
    assert "2025-11" in by_month
    assert "2026-02" in by_month
    assert by_month["2026-02"].value_usd_billion == 25.17
    print("✓ test_parse_ict_inline_trend_unicode_quotes")


def test_parse_ict_main_value():
    """ICT レポート: ○ (반도체 : XXX억 달러, XX.X%↑) パターン"""
    text = """
    2026년 2월 정보통신산업(ICT) 수출입 동향
    
    ○ (반도체 : 251.7억 달러, 160.8%↑) 글로벌 AI 서버 수요 확대
    """
    records = parse_ict_report_text(text)
    assert len(records) >= 1, f"Expected >=1 record, got {len(records)}"
    
    # report_ref = "2026-02" のレコードがあるはず
    feb = [r for r in records if r.ref_month == "2026-02"]
    assert len(feb) >= 1, f"No 2026-02 record found"
    r = feb[0]
    assert r.value_usd_billion == 25.17
    assert r.yoy_pct == 160.8
    print("✓ test_parse_ict_main_value")


def test_parse_ict_trend_table():
    """ICTレポート: PDF テキスト化されたトレンドテーブル"""
    text = """
    2025년 10월 정보통신산업(ICT) 수출입 동향
    
    반도체 수출 추이 (단위:억달러,%:전년동월대비)
    구분 '24.10  11    12   '25.1   2     3     4     5     6     7     8     9     10
    반도체 140.9 142.1 165.3 162.7 165.4 188.1 170.8 190.4 210.4 193.8 205.8 223.2 208.0
           (42.5)(22.0)(24.2)(-0.5) (0.2)(19.3)(33.8)(31.8)(31.1)(32.7)(28.4)(23.7)(22.0)
    
    컴퓨터·주변기기 수출 추이
    """
    records = parse_ict_report_text(text)
    assert len(records) == 13, f"Expected 13 records, got {len(records)}"
    
    r0 = records[0]
    assert r0.ref_month == "2024-10"
    assert r0.value_usd_billion == 14.09
    assert r0.yoy_pct == 42.5
    
    r12 = records[12]
    assert r12.ref_month == "2025-10"
    assert r12.value_usd_billion == 20.8
    assert r12.yoy_pct == 22.0
    
    print("✓ test_parse_ict_trend_table")


def test_parse_month_headers():
    """月ヘッダーパース"""
    header = "'24.10  11  12  '25.1  2  3  4  5  6  7  8  9  10"
    months = _parse_month_headers(header)
    expected = [
        "2024-10", "2024-11", "2024-12",
        "2025-01", "2025-02", "2025-03", "2025-04", "2025-05",
        "2025-06", "2025-07", "2025-08", "2025-09", "2025-10",
    ]
    assert months == expected, f"Got {months}"
    print("✓ test_parse_month_headers")


def test_parse_month_headers_year_rollover():
    """年をまたぐヘッダー"""
    header = "'25.10  11  12  '26.1  2"
    months = _parse_month_headers(header)
    expected = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]
    assert months == expected
    print("✓ test_parse_month_headers_year_rollover")


def test_parse_ict_inline_with_pct_first():
    """ICT: 반도체 수출이 102.7% 증가하며 205억 5000만 달러"""
    text = """
    2026년 1월 정보통신산업(ICT) 수출입 동향
    
    반도체 수출이 102.7% 증가하며 205억 5000만 달러 실적을 기록했다.
    """
    records = parse_ict_report_text(text)
    assert len(records) >= 1, f"Expected >=1, got {len(records)}"
    r = records[0]
    assert r.ref_month == "2026-01"
    assert abs(r.value_usd_billion - 20.55) < 0.1
    assert r.yoy_pct == 102.7
    print("✓ test_parse_ict_inline_with_pct_first")


def test_deduplicate():
    """重複排除テスト"""
    records = [
        SemiconductorExportRecord(
            ref_month="2025-03", value_usd_billion=13.1, yoy_pct=11.9,
            source_report="TRADE",
        ),
        SemiconductorExportRecord(
            ref_month="2025-03", value_usd_billion=13.1, yoy_pct=11.9,
            source_report="ICT",
        ),
        SemiconductorExportRecord(
            ref_month="2025-04", value_usd_billion=12.5, yoy_pct=8.0,
            source_report="TRADE",
        ),
    ]
    merged = deduplicate_records(records)
    assert len(merged) == 2
    assert merged[0].source_report == "ICT"  # ICT が優先
    assert merged[1].source_report == "TRADE"
    print("✓ test_deduplicate")


def run_all():
    tests = [
        test_parse_trade_ko_pattern1,
        test_parse_trade_ko_pattern2,
        test_parse_trade_ko_negative,
        test_parse_ict_inline_trend_real,
        test_parse_ict_inline_trend_unicode_quotes,
        test_parse_ict_main_value,
        test_parse_ict_trend_table,
        test_parse_month_headers,
        test_parse_month_headers_year_rollover,
        test_parse_ict_inline_with_pct_first,
        test_deduplicate,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: EXCEPTION {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
