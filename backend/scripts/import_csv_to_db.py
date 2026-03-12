"""
CSVファイルからeconomic_calendar_eventsテーブルへ過去データをインポートするスクリプト

FMPは直近1年分しか取得できないため、それ以前のデータをCSVから補填する。
既存データ（FMPからの取得分）は上書きせず、存在しない日付のみ追加する。

対象指標:
- ISM製造業景況指数 (ISM Manufacturing PMI)
- ISM非製造業景況指数 (ISM Services PMI)
- CB消費者信頼感指数 (CB Consumer Confidence)
- チャレンジャー人員削減数 (Challenger Job Cuts)
- レッドブック (Redbook YoY)
- コントロールグループ (Retail Sales Control Group MoM)
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .envファイルを読み込み（プロジェクトルートの親ディレクトリ）
env_path = project_root.parent / ".env"
load_dotenv(env_path)

from core.database import get_db_connection

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

# CSVファイルと指標のマッピング
CSV_CONFIGS = [
    {
        "file": "ISM製造業景況指数.csv",
        "event_name": "ISM Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "High",
        "date_format": "monthly",  # 2010/1 形式
        "value_type": "number",
    },
    {
        "file": "ISM非製造業景況指数.csv",
        "event_name": "ISM Services PMI",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "number",
    },
    {
        "file": "CB消費者信頼感指数.csv",
        "event_name": "CB Consumer Confidence",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "number",
    },
    {
        "file": "チャレンジャー人員削減数.csv",
        "event_name": "Challenger Job Cuts",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "number",
        "unit": "K",
    },
    {
        "file": "レッドブック（前年比）.csv",
        "event_name": "Redbook YoY",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Low",
        "date_format": "daily",  # 2015年01月06日 形式
        "value_type": "percent",
    },
    {
        "file": "コントロールグループ.csv",
        "event_name": "Retail Sales Control Group MoM",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "percent",
    },
    {
        "file": "中古住宅販売保留 （前月比）.csv",
        "event_name": "Pending Home Sales MoM",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "percent",
    },
    {
        "file": "中古住宅販売保留 （前年比）.csv",
        "event_name": "Pending Home Sales YoY",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "percent",
    },
    {
        "file": "中古住宅販売戸数.csv",
        "event_name": "Existing Home Sales",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "million",  # 5.05M形式
    },
    # S&P Global PMI
    {
        "file": "US S&P製造業PMI.csv",
        "event_name": "S&P Global Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "number",
    },
    {
        "file": "US S&PサービスPMI.csv",
        "event_name": "S&P Global Services PMI",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "number",
    },
    {
        "file": "US S&P総合PMI.csv",
        "event_name": "S&P Global Composite PMI",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "number",
    },
    # Japan BOJ Policy Rate
    {
        "file": "日銀金利.csv",
        "event_name": "BoJ Interest Rate Decision",
        "provider": "CSV_IMPORT",
        "country": "JP",
        "currency": "JPY",
        "impact": "High",
        "date_format": "boj_date",  # 2010-01-26 形式
        "value_type": "percent",
    },
    # Japan S&P Global PMI
    {
        "file": "JP S&P製造業PMI.csv",
        "event_name": "S&P Global Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "JP",
        "currency": "JPY",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "number",
    },
    {
        "file": "JP S&PサービスPMI.csv",
        "event_name": "S&P Global Services PMI",
        "provider": "CSV_IMPORT",
        "country": "JP",
        "currency": "JPY",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "number",
    },
    {
        "file": "JP S&P総合PMI.csv",
        "event_name": "S&P Global Composite PMI",
        "provider": "CSV_IMPORT",
        "country": "JP",
        "currency": "JPY",
        "impact": "High",
        "date_format": "monthly",
        "value_type": "number",
    },
    # Eurozone HCOB PMI (formerly S&P Global PMI)
    # FMPのユーロ圏データはcountry='EU'で保存されているため、CSVも同様に'EU'で保存
    {
        "file": "EU S&P製造業PMI.csv",
        "event_name": "HCOB Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "EU",
        "currency": "EUR",
        "impact": "High",
        "date_format": "monthly_utc",  # EUデータはUTC月初で保存
        "value_type": "number",
    },
    {
        "file": "EU S&PサービスPMI.csv",
        "event_name": "HCOB Services PMI",
        "provider": "CSV_IMPORT",
        "country": "EU",
        "currency": "EUR",
        "impact": "High",
        "date_format": "monthly_utc",  # EUデータはUTC月初で保存
        "value_type": "number",
    },
    {
        "file": "EU S&P総合PMI.csv",
        "event_name": "HCOB Composite PMI",
        "provider": "CSV_IMPORT",
        "country": "EU",
        "currency": "EUR",
        "impact": "High",
        "date_format": "monthly_utc",  # EUデータはUTC月初で保存
        "value_type": "number",
    },
    # Germany GfK Consumer Confidence
    # 注意: CSVの日付は翌月を指す（例: 2021/1 = 2021年1月分の予測値）
    # データはそのまま翌月として保存（date_offset_monthsは使用しない）
    {
        "file": "ドイツGfk消費者信頼感指数.csv",
        "event_name": "GfK Consumer Confidence",
        "provider": "CSV_IMPORT",
        "country": "DE",
        "currency": "EUR",
        "impact": "Medium",
        "date_format": "monthly_utc",  # ドイツデータはUTC月初で保存
        "value_type": "number",
    },
    # UK CBI Industrial Trends Orders
    {
        "file": "CBI製造業受注指数.csv",
        "event_name": "CBI Industrial Trends Orders",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "Medium",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "number",
    },
    # UK S&P Global Manufacturing PMI
    {
        "file": "UK S&P製造業PMI.csv",
        "event_name": "S&P Global Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "High",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "number",
    },
    # UK S&P Global Services PMI
    {
        "file": "UK S&PサービスPMI.csv",
        "event_name": "S&P Global Services PMI",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "High",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "number",
    },
    # UK S&P Global Composite PMI
    {
        "file": "UK S&P総合PMI.csv",
        "event_name": "S&P Global Composite PMI",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "High",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "number",
    },
    # UK BRC Retail Sales Monitor
    # 注意: CSVの日付はデータ対象月を指す（例: 2025/12 = 12月分のデータ）
    # FMPは発表月で保存されるため、CSVも発表月に合わせて+1ヶ月オフセット
    # 例: 2025/12データ → 2026/1に発表 → 2026-01-01として保存
    {
        "file": "BRC小売売上高前年比.csv",
        "event_name": "BRC Retail Sales Monitor YoY",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "Medium",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "percent",
        "date_offset_months": 1,  # データ対象月→発表月（+1ヶ月）
    },
    # UK GfK Consumer Confidence
    # 注意: CSVの日付はデータ対象月を指す（例: 2025/12 = 12月分のデータ）
    # FMPは発表月で保存されるため、CSVも発表月に合わせて+1ヶ月オフセット
    {
        "file": "UK GfK消費者信頼感指数.csv",
        "event_name": "Consumer Confidence",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "Medium",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "number",
        "date_offset_months": 1,  # データ対象月→発表月（+1ヶ月）
    },
    # UK RICS House Price Balance
    # CSVの日付はデータ対象月を指す（例: 2025/12 = 12月分のデータ）
    # CSVはデータ対象月のまま保存し、サービス側で表示用に調整
    {
        "file": "RICS住宅価格.csv",
        "event_name": "RICS House Price Balance",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "Medium",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "number",
        # date_offset_monthsなし - データ対象月のまま保存
    },
    # UK Halifax House Price Index
    # CSVの日付はデータ対象月を指す（例: 2025/12 = 12月分のデータ）
    {
        "file": "ハリファックス住宅価格指数前月比.csv",
        "event_name": "Halifax House Price Index MoM",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "Medium",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "percent",
    },
    {
        "file": "ハリファックス住宅価格指数前年比.csv",
        "event_name": "Halifax House Price Index YoY",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "Medium",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "percent",
    },
    # UK Rightmove House Price Index
    # CSVの日付はデータ対象月を指す（例: 2025/12 = 12月分のデータ）
    {
        "file": "ライトムーブ住宅価格指数前月比.csv",
        "event_name": "Rightmove House Price Index MoM",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "Medium",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "percent",
    },
    {
        "file": "ライトムーブ住宅価格指数前年比.csv",
        "event_name": "Rightmove House Price Index YoY",
        "provider": "CSV_IMPORT",
        "country": "UK",
        "currency": "GBP",
        "impact": "Medium",
        "date_format": "monthly_utc",  # UKデータはUTC月初で保存
        "value_type": "percent",
    },
    # Germany S&P Global PMI
    {
        "file": "DE S&P製造業PMI.csv",
        "event_name": "S&P Global Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "DE",
        "currency": "EUR",
        "impact": "High",
        "date_format": "monthly_utc",  # ドイツデータはUTC月初で保存
        "value_type": "number",
    },
    {
        "file": "DE S&PサービスPMI.csv",
        "event_name": "S&P Global Services PMI",
        "provider": "CSV_IMPORT",
        "country": "DE",
        "currency": "EUR",
        "impact": "High",
        "date_format": "monthly_utc",  # ドイツデータはUTC月初で保存
        "value_type": "number",
    },
    {
        "file": "DE S&P総合PMI.csv",
        "event_name": "S&P Global Composite PMI",
        "provider": "CSV_IMPORT",
        "country": "DE",
        "currency": "EUR",
        "impact": "High",
        "date_format": "monthly_utc",  # ドイツデータはUTC月初で保存
        "value_type": "number",
    },
    # France HCOB PMI
    {
        "file": "FR S&P製造業PMI.csv",
        "event_name": "HCOB Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "FR",
        "currency": "EUR",
        "impact": "High",
        "date_format": "monthly_utc",  # フランスデータはUTC月初で保存
        "value_type": "number",
    },
    {
        "file": "FR S&PサービスPMI.csv",
        "event_name": "HCOB Services PMI",
        "provider": "CSV_IMPORT",
        "country": "FR",
        "currency": "EUR",
        "impact": "High",
        "date_format": "monthly_utc",  # フランスデータはUTC月初で保存
        "value_type": "number",
    },
    {
        "file": "FR S&P総合PMI.csv",
        "event_name": "HCOB Composite PMI",
        "provider": "CSV_IMPORT",
        "country": "FR",
        "currency": "EUR",
        "impact": "High",
        "date_format": "monthly_utc",  # フランスデータはUTC月初で保存
        "value_type": "number",
    },
    # Canada Ivey PMI
    {
        "file": "IveyPMI.csv",
        "event_name": "Ivey PMI s.a",
        "provider": "CSV_IMPORT",
        "country": "CA",
        "currency": "CAD",
        "impact": "Medium",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    # Canada S&P Global PMI (3 series)
    {
        "file": "カナダ製造業PMI.csv",
        "event_name": "S&P Global Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "CA",
        "currency": "CAD",
        "impact": "High",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    {
        "file": "カナダサービスPMI.csv",
        "event_name": "S&P Global Services PMI",
        "provider": "CSV_IMPORT",
        "country": "CA",
        "currency": "CAD",
        "impact": "High",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    {
        "file": "カナダ総合PMI.csv",
        "event_name": "S&P Global Composite PMI",
        "provider": "CSV_IMPORT",
        "country": "CA",
        "currency": "CAD",
        "impact": "High",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    # Australia S&P Global PMI (3 series)
    {
        "file": "AU S&P製造業PMI.csv",
        "event_name": "S&P Global Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "AU",
        "currency": "AUD",
        "impact": "High",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    {
        "file": "AU S&PサービスPMI.csv",
        "event_name": "S&P Global Services PMI",
        "provider": "CSV_IMPORT",
        "country": "AU",
        "currency": "AUD",
        "impact": "High",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    {
        "file": "AU S&P総合PMI.csv",
        "event_name": "S&P Global Composite PMI",
        "provider": "CSV_IMPORT",
        "country": "AU",
        "currency": "AUD",
        "impact": "High",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    # Australia Inflation Expectations (Melbourne Institute)
    {
        "file": "豪インフレ期待.csv",
        "event_name": "Inflation Expectations",
        "provider": "CSV_IMPORT",
        "country": "AU",
        "currency": "AUD",
        "impact": "Medium",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    # Westpac Consumer Confidence Index
    {
        "file": "Westpac消費者信頼感指数.csv",
        "event_name": "Westpac Consumer Confidence Index",
        "provider": "CSV_IMPORT",
        "country": "AU",
        "currency": "AUD",
        "impact": "Medium",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    # Westpac Consumer Confidence Change (MoM%)
    {
        "file": "Westpac消費者信頼感指数前月比.csv",
        "event_name": "Westpac Consumer Confidence Change",
        "provider": "CSV_IMPORT",
        "country": "AU",
        "currency": "AUD",
        "impact": "Medium",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    # NAB Business Confidence Index
    {
        "file": "NAB企業信頼感指数.csv",
        "event_name": "NAB Business Confidence",
        "provider": "CSV_IMPORT",
        "country": "AU",
        "currency": "AUD",
        "impact": "Medium",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    # China Loan Prime Rate 1Y
    {
        "file": "ローンプライムレート.csv",
        "event_name": "Loan Prime Rate 1Y",
        "provider": "CSV_IMPORT",
        "country": "CN",
        "currency": "CNY",
        "impact": "High",
        "date_format": "cn_lpr",  # 2019/09/20 形式
        "value_type": "percent",
    },
    # China Loan Prime Rate 5Y
    {
        "file": "ローンプライムレート5Y.csv",
        "event_name": "Loan Prime Rate 5Y",
        "provider": "CSV_IMPORT",
        "country": "CN",
        "currency": "CNY",
        "impact": "High",
        "date_format": "cn_lpr_5y",  # 2023年8月21日 (8月) 形式
        "value_type": "percent",
    },
    # China House Price Index YoY
    {
        "file": "中国住宅価格指数.csv",
        "event_name": "House Price Index YoY",
        "provider": "CSV_IMPORT",
        "country": "CN",
        "currency": "CNY",
        "impact": "Medium",
        "date_format": "monthly_utc",  # 2011/1 形式
        "value_type": "percent",
    },
    # China Caixin Manufacturing PMI
    {
        "file": "中国財新製造業PMI.csv",
        "event_name": "Caixin Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "CN",
        "currency": "CNY",
        "impact": "High",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    # China Caixin Services PMI
    {
        "file": "中国財新サービス業PMI.csv",
        "event_name": "Caixin Services PMI",
        "provider": "CSV_IMPORT",
        "country": "CN",
        "currency": "CNY",
        "impact": "High",
        "date_format": "monthly_utc",
        "value_type": "number",
    },
    # Taiwan S&P Global Manufacturing PMI
    {
        "file": "台湾製造業PMI.csv",
        "event_name": "S&P Global Manufacturing PMI",
        "provider": "CSV_IMPORT",
        "country": "TW",
        "currency": "TWD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "number",
    },
    # South Korean Exports YoY
    {
        "file": "韓国輸出.csv",
        "event_name": "Exports YoY",
        "provider": "CSV_IMPORT",
        "country": "KR",
        "currency": "KRW",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "number",
    },
    # Taiwan Export Orders YoY
    {
        "file": "台湾輸出受注.csv",
        "event_name": "Export Orders YoY",
        "provider": "CSV_IMPORT",
        "country": "TW",
        "currency": "TWD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "number",
    },
    # Taiwan Electrical Equipment Exports (百萬美元)
    {
        "file": "台湾電気機器輸出.csv",
        "event_name": "Electrical Equipment Exports",
        "provider": "CSV_IMPORT",
        "country": "TW",
        "currency": "TWD",
        "impact": "Medium",
        "date_format": "monthly",
        "value_type": "comma_number",
    },
    # API Weekly Crude Oil Stock Change
    {
        "file": "API週間原油在庫.csv",
        "event_name": "API Crude Oil Stock Change",
        "provider": "CSV_IMPORT",
        "country": "US",
        "currency": "USD",
        "impact": "Medium",
        "date_format": "investing_date",  # "Nov 29, 2017" 形式
        "value_type": "million",  # 1.821M形式
    },
]


def parse_date_monthly(date_str: str, time_str: str) -> datetime:
    """
    月次データの日付をパース (2010/1 形式)
    時間は JST として解釈し、UTC に変換
    """
    year, month = date_str.split("/")
    year = int(year)
    month = int(month)

    # 時間をパース
    hour, minute = 0, 0
    if time_str and ":" in time_str:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

    # JST で作成し UTC に変換
    dt_jst = datetime(year, month, 1, hour, minute, tzinfo=JST)
    return dt_jst.astimezone(UTC)


def parse_date_monthly_utc(date_str: str, time_str: str) -> datetime:
    """
    月次データの日付をパース (2010/1 形式)
    タイムゾーン変換なしでUTC月初12:00として保存（非日本データ用）
    """
    year, month = date_str.split("/")
    year = int(year)
    month = int(month)

    # UTCの月初12:00として作成（タイムゾーン変換による月ずれを防ぐ）
    return datetime(year, month, 1, 12, 0, tzinfo=UTC)


def parse_date_daily(date_str: str, time_str: str) -> datetime:
    """
    日次データの日付をパース (2015年01月06日 形式)
    時間は JST として解釈し、UTC に変換
    """
    # 2015年01月06日 → 2015-01-06
    date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "")
    parts = date_str.split("-")
    year = int(parts[0])
    month = int(parts[1])
    day = int(parts[2])

    # 時間をパース
    hour, minute = 0, 0
    if time_str and ":" in time_str:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

    # JST で作成し UTC に変換
    dt_jst = datetime(year, month, day, hour, minute, tzinfo=JST)
    return dt_jst.astimezone(UTC)


def parse_date_cn_lpr(date_str: str, time_str: str) -> datetime:
    """
    中国LPR（1Y）日付をパース
    - 通常形式: 2019/09/20
    - 日本語形式: 2025年1月20日 (1月)  ← 一部レコードで混在
    時間は CST (UTC+8) として解釈し、UTC に変換
    """
    import re
    date_str = date_str.strip()

    # 日本語形式を先にチェック: "YYYY年M月D日"
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_str)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        # スラッシュ/ハイフン形式: 2019/09/20
        parts = re.split(r"[/\-]", date_str)
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2]) if len(parts) > 2 else 1

    hour, minute = 10, 15
    if time_str and ":" in time_str:
        tp = time_str.split(":")
        hour = int(tp[0])
        minute = int(tp[1]) if len(tp) > 1 else 0

    CST = ZoneInfo("Asia/Shanghai")
    dt_cst = datetime(year, month, day, hour, minute, tzinfo=CST)
    return dt_cst.astimezone(UTC)


def parse_date_cn_lpr_5y(date_str: str, time_str: str) -> datetime:
    """
    中国LPR（5Y）日付をパース (2023年8月21日 (8月) 形式)
    時間は CST (UTC+8) として解釈し、UTC に変換
    """
    import re
    # Extract year, month, day from "2023年8月21日 (8月)" pattern
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_str)
    if not m:
        raise ValueError(f"Cannot parse CN LPR 5Y date: {date_str}")
    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))

    hour, minute = 10, 15
    if time_str and ":" in time_str:
        tp = time_str.split(":")
        hour = int(tp[0])
        minute = int(tp[1]) if len(tp) > 1 else 0

    CST = ZoneInfo("Asia/Shanghai")
    dt_cst = datetime(year, month, day, hour, minute, tzinfo=CST)
    return dt_cst.astimezone(UTC)


def parse_date_investing(date_str: str, time_str: str) -> datetime:
    """
    Investing.com形式の日付をパース ("Nov 29, 2017" / "Jan 04, 2018" 形式)
    時間は EST として解釈し、UTC に変換
    """
    date_str = date_str.strip().strip('"')
    # "Nov 29, 2017" → datetime
    dt = datetime.strptime(date_str, "%b %d, %Y")

    hour, minute = 21, 30  # デフォルトは EST 21:30
    if time_str and ":" in str(time_str):
        tp = str(time_str).strip().split(":")
        hour = int(tp[0])
        minute = int(tp[1]) if len(tp) > 1 else 0

    # JST として解釈（CSVの時間はJST）し UTC に変換
    dt_jst = datetime(dt.year, dt.month, dt.day, hour, minute, tzinfo=JST)
    return dt_jst.astimezone(UTC)


def parse_date_boj(date_str: str, time_str: str) -> datetime:
    """
    日銀金利データの日付をパース (2010-01-26 形式)
    時間は JST として解釈し、UTC に変換
    """
    parts = date_str.split("-")
    year = int(parts[0])
    month = int(parts[1])
    day = int(parts[2])

    # 時間をパース（デフォルトは12:00 JST = 日銀発表時刻の中間値）
    hour, minute = 12, 0
    if time_str and ":" in time_str:
        time_parts = time_str.split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1]) if len(time_parts) > 1 else 0

    # JST で作成し UTC に変換
    dt_jst = datetime(year, month, day, hour, minute, tzinfo=JST)
    return dt_jst.astimezone(UTC)


def parse_value(value_str, value_type: str) -> float:
    """値をパース（%やMを除去など）"""
    if pd.isna(value_str) or value_str == "" or value_str is None:
        return None

    value_str = str(value_str).strip()
    if value_type == "percent":
        value_str = value_str.replace("%", "")
    elif value_type == "million":
        # 5.05M → 5.05（百万戸単位を数値に変換）
        value_str = value_str.replace("M", "")
    elif value_type == "comma_number":
        # "7,558" → 7558（カンマ区切り数値）
        value_str = value_str.replace(",", "")

    try:
        return float(value_str)
    except (ValueError, TypeError):
        return None


def get_existing_dates(conn, event_pattern: str, country: str = "US") -> set:
    """既存データの日付を取得"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT datetime_utc::date
            FROM economic_calendar_events
            WHERE country = %s
              AND event ILIKE %s
        """, (country, f"%{event_pattern}%",))
        return {row[0] for row in cur.fetchall()}


def import_csv(config: dict, csv_dir: Path, dry_run: bool = False) -> dict:
    """CSVファイルをDBにインポート"""
    file_path = csv_dir / config["file"]

    if not file_path.exists():
        return {"status": "skip", "reason": f"File not found: {file_path}"}

    print(f"\n{'='*60}")
    print(f"Processing: {config['event_name']}")
    print(f"File: {file_path}")
    print(f"{'='*60}")

    # CSV読み込み（タブ区切りも自動認識）
    try:
        df = pd.read_csv(file_path, encoding="utf-8", sep=None, engine='python')
    except Exception:
        df = pd.read_csv(file_path, encoding="utf-8")
    print(f"Total rows in CSV: {len(df)}")

    # 既存データの日付を取得
    with get_db_connection() as conn:
        existing_dates = get_existing_dates(conn, config["event_name"], config["country"])
        print(f"Existing dates in DB: {len(existing_dates)}")

        inserted = 0
        skipped = 0
        errors = 0

        with conn.cursor() as cur:
            for _, row in df.iterrows():
                try:
                    # 日付をパース
                    # 日銀金利CSVは "公表日時" カラム、他は "公表日" カラム
                    if "公表日時" in row:
                        date_str = str(row["公表日時"])
                    elif "公表日" in row:
                        date_str = str(row["公表日"])
                    else:
                        print(f"  Warning: No date column found in row: {row.to_dict()}")
                        continue
                    # 時間カラム名のバリエーション対応
                    time_str = ""
                    if "時間" in row:
                        time_str = str(row["時間"])
                    elif "発表時間" in row:
                        time_str = str(row["発表時間"])
                    elif "時刻" in row:
                        time_str = str(row["時刻"])

                    if config["date_format"] == "monthly":
                        dt_utc = parse_date_monthly(date_str, time_str)
                    elif config["date_format"] == "monthly_utc":
                        dt_utc = parse_date_monthly_utc(date_str, time_str)
                    elif config["date_format"] == "boj_date":
                        dt_utc = parse_date_boj(date_str, time_str)
                    elif config["date_format"] == "cn_lpr":
                        dt_utc = parse_date_cn_lpr(date_str, time_str)
                    elif config["date_format"] == "cn_lpr_5y":
                        dt_utc = parse_date_cn_lpr_5y(date_str, time_str)
                    elif config["date_format"] == "investing_date":
                        dt_utc = parse_date_investing(date_str, time_str)
                    else:
                        dt_utc = parse_date_daily(date_str, time_str)

                    # 日付オフセットを適用（発表月→データ対象月など）
                    date_offset = config.get("date_offset_months", 0)
                    if date_offset != 0:
                        from dateutil.relativedelta import relativedelta
                        dt_utc = dt_utc + relativedelta(months=date_offset)

                    # 既存チェック
                    if dt_utc.date() in existing_dates:
                        skipped += 1
                        continue

                    # 値をパース
                    actual = parse_value(row["結果"], config["value_type"])
                    estimate = parse_value(row.get("予想"), config["value_type"])
                    previous = parse_value(row.get("前回"), config["value_type"])

                    if actual is None:
                        skipped += 1
                        continue

                    # 期間ラベルを生成
                    if config["date_format"] in ("monthly", "monthly_utc"):
                        period_label = dt_utc.strftime("%b")  # Jan, Feb, etc.
                    else:
                        period_label = None

                    # event_key を生成（国コード含む）
                    event_key = f"{config['country']}_{config['event_name']}_{dt_utc.strftime('%Y%m%d')}"

                    if dry_run:
                        print(f"  [DRY RUN] Would insert: {dt_utc.date()} - {actual}")
                        inserted += 1
                        continue

                    # DBに挿入
                    cur.execute("""
                        INSERT INTO economic_calendar_events (
                            provider, event_key, country, currency, event, event_period,
                            datetime_raw, datetime_utc, has_time, impact,
                            previous, estimate, actual, raw_json
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s
                        )
                        ON CONFLICT (provider, event_key) DO NOTHING
                    """, (
                        config["provider"],
                        event_key,
                        config["country"],
                        config["currency"],
                        config["event_name"],
                        period_label,
                        dt_utc.isoformat(),
                        dt_utc,
                        True if time_str else False,
                        config["impact"],
                        previous,
                        estimate,
                        actual,
                        "{}",
                    ))
                    inserted += 1

                except Exception as e:
                    print(f"  Error processing row: {row.to_dict()} - {e}")
                    errors += 1

            if not dry_run:
                conn.commit()

        result = {
            "status": "success",
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }
        print(f"Result: {result}")
        return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import CSV data to economic_calendar_events table")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert data")
    parser.add_argument("--indicator", type=str, help="Only import specific indicator (e.g., 'ISM Manufacturing')")
    args = parser.parse_args()

    # CSVファイルのディレクトリ（backend/data/csv_import）
    csv_dir = Path(__file__).parent.parent / "data" / "csv_import"

    print(f"CSV Directory: {csv_dir}")
    print(f"Dry Run: {args.dry_run}")

    results = {}

    for config in CSV_CONFIGS:
        if args.indicator and args.indicator.lower() not in config["event_name"].lower():
            continue

        result = import_csv(config, csv_dir, dry_run=args.dry_run)
        results[config["event_name"]] = result

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    total_inserted = 0
    total_skipped = 0
    total_errors = 0

    for event_name, result in results.items():
        print(f"{event_name}:")
        print(f"  Status: {result.get('status')}")
        if result.get("status") == "success":
            print(f"  Inserted: {result.get('inserted')}")
            print(f"  Skipped: {result.get('skipped')}")
            print(f"  Errors: {result.get('errors')}")
            total_inserted += result.get("inserted", 0)
            total_skipped += result.get("skipped", 0)
            total_errors += result.get("errors", 0)
        else:
            print(f"  Reason: {result.get('reason')}")

    print(f"\nTotal: Inserted={total_inserted}, Skipped={total_skipped}, Errors={total_errors}")


if __name__ == "__main__":
    main()
