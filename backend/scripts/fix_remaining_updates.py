"""
残りの指標ID・名前を直接更新
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from backend.core.database import get_db_connection

# フロントエンドと紐付けあり（ID変換＋日本語名）
frontend_mappings = [
    # 景況感
    ('us_ism_manufacturing', 'ism_manufacturing', 'ISM製造業景況指数'),
    ('us_ism_services', 'ism_non_manufacturing', 'ISM非製造業景況指数'),
    ('us_empire_state', 'empire_state', 'NY連銀製造業景気指数'),
    ('us_philly_fed', 'philadelphia_fed', 'フィラデルフィア連銀製造業景気指数'),
    ('us_nfib', 'nfib', 'NFIB中小企業楽観指数'),
    # 生産
    ('us_industrial_production', 'industrial_production', '鉱工業生産'),
    ('us_capacity_utilization', 'capacity_utilization', '設備稼働率'),
    ('us_durable_goods', 'durable_goods', '耐久財受注'),
    # 雇用
    ('us_unemployment_rate', 'unemployment_rate', '失業率'),
    ('us_nonfarm_payrolls', 'nonfarm_payrolls', '非農業部門雇用者数'),
    ('us_adp_employment', 'adp_employment', 'ADP雇用者数'),
    ('us_jolts_openings', 'jolts_openings', 'JOLTS求人件数'),
    ('us_participation_rate', 'labor_force_participation', '労働参加率'),
    ('us_initial_claims', 'initial_claims', '新規失業保険申請件数'),
    ('us_continuing_claims', 'continued_claims', '継続受給者数'),
    ('us_challenger_job_cuts', 'challenger_job_cuts', 'チャレンジャー人員削減'),
    # 賃金
    ('us_average_hourly_earnings', 'average_hourly_earnings', '平均時給'),
    ('us_employment_cost_index', 'employment_cost_index', '雇用コスト指数'),
    ('us_unit_labor_costs', 'unit_labor_cost', '単位労働コスト'),
    # 消費
    ('us_retail_sales', 'retail_sales', '小売売上高'),
    ('us_cb_consumer_confidence', 'cb_consumer_confidence', 'CB消費者信頼感指数'),
    ('us_michigan_sentiment', 'michigan_consumer_sentiment', 'ミシガン大学消費者信頼感指数'),
    ('us_personal_income', 'personal_income', '個人所得'),
    ('us_pce', 'pce', 'PCE（個人消費支出）'),
]

# フロントエンド未実装（日本語名のみ、IDはNULLに）
non_frontend_mappings = [
    # 金融政策
    ('us_fed_rate', 'FRB金利決定'),
    ('us_interest_rate_projection_1st', '金利見通し（1年目）'),
    ('us_interest_rate_projection_2nd', '金利見通し（2年目）'),
    ('us_interest_rate_projection_3rd', '金利見通し（3年目）'),
    ('us_interest_rate_projection_current', '金利見通し（現在）'),
    ('us_interest_rate_projection_longer', '金利見通し（長期）'),
    ('us_fomc_projections', 'FOMC経済予測'),
    ('us_monetary_policy_report', '金融政策報告書'),
    # 雇用（フロントエンド未実装）
    ('us_nonfarm_payrolls_private', '非農業部門雇用者数（民間）'),
    ('us_u6_unemployment_rate', 'U-6失業率'),
    ('us_jobless_claims_4wk_avg', '失業保険申請件数4週平均'),
    ('us_jolts_quits', 'JOLTS自発的離職者数'),
    ('us_nonfarm_productivity', '非農業部門生産性'),
    # GDP
    ('us_gdp_growth', 'GDP成長率'),
    ('us_gdp_price_index', 'GDPデフレーター'),
    ('us_gdp_sales', 'GDP売上高'),
    ('us_atlanta_fed_gdpnow', 'アトランタ連銀GDPNow'),
    # インフレ・物価
    ('us_cpi', '消費者物価指数（CPI）'),
    ('us_core_cpi', 'コアCPI'),
    ('us_ppi', '生産者物価指数（PPI）'),
    ('us_core_ppi', 'コアPPI'),
    ('us_ppi_ex_food_energy_trade', 'PPI（除く食品・エネルギー・貿易）'),
    ('us_core_pce', 'コアPCE'),
    ('us_import_prices', '輸入物価'),
    ('us_export_prices', '輸出物価'),
    ('us_inflation_expectations', 'インフレ期待'),
    # 消費（フロントエンド未実装）
    ('us_retail_sales_ex_autos', '小売売上高（除く自動車）'),
    ('us_retail_sales_ex_gas_autos', '小売売上高（除くガソリン・自動車）'),
    ('us_personal_spending', '個人支出'),
    ('us_real_consumer_spending', '実質個人消費'),
    ('us_real_earnings', '実質賃金'),
    ('us_michigan_expectations', 'ミシガン大学期待指数'),
    ('us_michigan_current', 'ミシガン大学現況指数'),
    ('us_michigan_inflation_exp', 'ミシガン大学インフレ期待'),
    ('us_michigan_5y_inflation_exp', 'ミシガン大学5年インフレ期待'),
    # 製造業（フロントエンド未実装）
    ('us_ism_manufacturing_employment', 'ISM製造業雇用'),
    ('us_ism_manufacturing_new_orders', 'ISM製造業新規受注'),
    ('us_ism_manufacturing_prices', 'ISM製造業仕入価格'),
    ('us_ism_services_employment', 'ISM非製造業雇用'),
    ('us_ism_services_new_orders', 'ISM非製造業新規受注'),
    ('us_ism_services_prices', 'ISM非製造業仕入価格'),
    ('us_ism_services_activity', 'ISM非製造業企業活動'),
    ('us_manufacturing_production', '製造業生産'),
    ('us_factory_orders', '製造業受注'),
    ('us_durable_goods_ex_defense', '耐久財受注（除く防衛）'),
    ('us_durable_goods_ex_transport', '耐久財受注（除く輸送機器）'),
    # 地域連銀（フロントエンド未実装）
    ('us_philly_fed_business', 'フィラデルフィア連銀企業見通し'),
    ('us_philly_fed_capex', 'フィラデルフィア連銀設備投資'),
    ('us_philly_fed_employment', 'フィラデルフィア連銀雇用'),
    ('us_philly_fed_new_orders', 'フィラデルフィア連銀新規受注'),
    ('us_philly_fed_prices', 'フィラデルフィア連銀仕入価格'),
    # 住宅
    ('us_housing_starts', '住宅着工件数'),
    ('us_building_permits', '建築許可件数'),
    ('us_existing_home_sales', '中古住宅販売件数'),
    ('us_new_home_sales', '新築住宅販売件数'),
    ('us_pending_home_sales', '中古住宅販売保留件数'),
    ('us_house_price_index', '住宅価格指数'),
    ('us_case_shiller', 'S&P/ケース・シラー住宅価格'),
    ('us_nahb', 'NAHB住宅市場指数'),
    # PMI
    ('us_sp_composite_pmi', 'S&Pグローバル総合PMI'),
    ('us_sp_manufacturing_pmi', 'S&Pグローバル製造業PMI'),
    ('us_sp_services_pmi', 'S&Pグローバルサービス業PMI'),
    # その他
    ('us_opec_meeting', 'OPEC会合'),
    ('us_opec_report', 'OPEC月報'),
]

def main():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # フロントエンド紐付け有り
            print("フロントエンド紐付け有りの指標を更新...")
            frontend_count = 0
            for old_id, new_id, name in frontend_mappings:
                cur.execute(
                    "UPDATE indicator_event_mapping SET econalpha_id = %s, econalpha_name = %s WHERE econalpha_id = %s",
                    (new_id, name, old_id)
                )
                frontend_count += cur.rowcount

            # フロントエンド紐付け無し（IDをNULLに）
            print("フロントエンド未実装の指標を更新...")
            non_frontend_count = 0
            for old_id, name in non_frontend_mappings:
                cur.execute(
                    "UPDATE indicator_event_mapping SET econalpha_id = NULL, econalpha_name = %s WHERE econalpha_id = %s",
                    (name, old_id)
                )
                non_frontend_count += cur.rowcount

            conn.commit()
            print(f"\n完了:")
            print(f"  フロントエンドID変換: {frontend_count}件")
            print(f"  日本語名のみ追加: {non_frontend_count}件")

            # 確認
            print("\n=== 確認 ===")
            cur.execute("""
                SELECT country, COUNT(*) as total, COUNT(econalpha_id) as with_id
                FROM indicator_event_mapping
                GROUP BY country
                ORDER BY country
            """)
            print("国 | 合計 | フロントID有")
            for row in cur.fetchall():
                print(f"{row[0]} | {row[1]} | {row[2]}")

            print("\n=== フロントエンドID有りのUS指標 ===")
            cur.execute("""
                SELECT econalpha_id, econalpha_name
                FROM indicator_event_mapping
                WHERE country = 'US' AND econalpha_id IS NOT NULL
                ORDER BY econalpha_id
            """)
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]}")

if __name__ == "__main__":
    main()
