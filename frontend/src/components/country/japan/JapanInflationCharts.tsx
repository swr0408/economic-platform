/**
 * 日本物価チャート群
 *
 * 日本のインフレ関連指標を表示
 * - 全国消費者物価指数（CPI）
 * - 東京都区部消費者物価指数（CPI）- 速報
 * - 企業物価指数（CGPI）
 * - 企業物価指数：飲食料品・農林水産物
 * - 輸入・輸出物価指数
 * - 企業向けサービス価格指数（SPPI）
 * - POS-UVPI（消費者購買単価指数）
 * - GDPギャップ（内閣府）
 * - GDPギャップ（日銀）
 */

import NationalCPIChart from './price/NationalCPIChart'
import JapanCPICategoriesCard from './price/JapanCPICategoriesTable'
import TokyoCPIChart from './price/TokyoCPIChart'
import JapanCGPIChart from './price/JapanCGPIChart'
import JapanCGPIFoodAgricultureChart from './price/JapanCGPIFoodAgricultureChart'
import JapanImportExportPriceChart from './price/JapanImportExportPriceChart'
import JapanSPPIChart from './price/JapanSPPIChart'
import JapanPosUvpiChart from './price/JapanPosUvpiChart'
import JapanGDPGapChart from './economy/JapanGDPGapChart'
import BOJGDPGapChart from './price/BOJGDPGapChart'

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

      {/* 企業物価指数：飲食料品・農林水産物 */}
      <div id="cgpi-food-agriculture">
        <JapanCGPIFoodAgricultureChart />
      </div>

      {/* 輸入・輸出物価指数 */}
      <div id="import-export-price">
        <JapanImportExportPriceChart />
      </div>

      {/* POS-UVPI（消費者購買単価指数） */}
      <div id="pos-uvpi">
        <JapanPosUvpiChart />
      </div>

      {/* GDPギャップ（内閣府） */}
      <div id="gdp-gap">
        <JapanGDPGapChart />
      </div>

      {/* GDPギャップ（日銀） */}
      <div id="boj-gdp-gap">
        <BOJGDPGapChart />
      </div>
    </div>
  )
}
