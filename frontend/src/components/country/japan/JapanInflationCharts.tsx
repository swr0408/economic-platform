/**
 * 日本物価チャート群
 *
 * 日本のインフレ関連指標を表示
 * - 全国消費者物価指数（CPI）
 * - 東京都区部消費者物価指数（CPI）- 速報
 * - 企業物価指数（CGPI）
 * - 企業向けサービス価格指数（SPPI）
 */

import NationalCPIChart from './price/NationalCPIChart'
import JapanCPICategoriesCard from './price/JapanCPICategoriesTable'
import TokyoCPIChart from './price/TokyoCPIChart'
import JapanCGPIChart from './price/JapanCGPIChart'
import JapanSPPIChart from './price/JapanSPPIChart'

export default function JapanInflationCharts() {
  return (
    <div className="country-chart-stack">
      {/* 全国消費者物価指数（CPI） */}
      <div id="national-cpi">
        <NationalCPIChart />
      </div>

      {/* CPI 10大費目別 */}
      <div id="cpi-categories">
        <JapanCPICategoriesCard />
      </div>

      {/* 東京都区部消費者物価指数（CPI）- 速報 */}
      <div id="tokyo-cpi">
        <TokyoCPIChart />
      </div>

      {/* 企業向けサービス価格指数（SPPI） */}
      <div id="sppi">
        <JapanSPPIChart />
      </div>

      {/* 企業物価指数（CGPI） */}
      <div id="cgpi">
        <JapanCGPIChart />
      </div>
    </div>
  )
}
