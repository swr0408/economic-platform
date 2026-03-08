import { useGlobalEconomyDashboard } from '../../../hooks/useDashboardData'
import GlobalManufacturingPmiChart from './economy/GlobalManufacturingPmiChart'
import EconomicSurpriseIndexChart from './economy/EconomicSurpriseIndexChart'
import KomtraxChart from './economy/KomtraxChart'
import EpuChart from './economy/EpuChart'
import SemiconductorSalesChart from './economy/SemiconductorSalesChart'
import SouthKoreanExportsChart from './economy/SouthKoreanExportsChart'
import TaiwanManufacturingPmiChart from './economy/TaiwanManufacturingPmiChart'
import TaiwanExportOrdersChart from './economy/TaiwanExportOrdersChart'
import TaiwanElectricalEquipmentExportsChart from './economy/TaiwanElectricalEquipmentExportsChart'
import TaiwanPmiOutlookChart from './economy/TaiwanPmiOutlookChart'
import ChinaShanghaiContainerFreightIndexChart from './economy/ChinaShanghaiContainerFreightIndexChart'
import BalticDryIndexChart from './economy/BalticDryIndexChart'

export default function GlobalEconomyCharts() {
  const { data: dashboardResponse } = useGlobalEconomyDashboard()
  const dashboardData = dashboardResponse?.data ?? null

  return (
    <div>
      {/* J.P.Morgan グローバル製造業PMI */}
      <GlobalManufacturingPmiChart
        data={dashboardData?.jpmorgan_global_manufacturing_pmi ?? null}
      />

      {/* エコノミックサプライズ指数 */}
      <EconomicSurpriseIndexChart />

      {/* Komtrax（車両稼働時間） */}
      <KomtraxChart />

      {/* 経済政策不確実性指数（EPU） */}
      <EpuChart
        data={dashboardData?.global_epu ?? null}
      />

      {/* WSTS半導体売上高 */}
      <SemiconductorSalesChart
        data={dashboardData?.semiconductor_sales ?? null}
      />

      {/* 韓国輸出（前年比） */}
      <SouthKoreanExportsChart
        data={dashboardData?.south_korean_exports ?? null}
      />

      {/* 台湾輸出受注（前年比） */}
      <TaiwanExportOrdersChart
        data={dashboardData?.taiwan_export_orders ?? null}
      />

      {/* 台湾電気機器輸出 */}
      <TaiwanElectricalEquipmentExportsChart
        data={dashboardData?.taiwan_electrical_equipment_exports ?? null}
      />

      {/* 台湾製造業PMI（S&P Global） */}
      <TaiwanManufacturingPmiChart
        data={dashboardData?.taiwan_manufacturing_pmi ?? null}
      />

      {/* 台湾PMI先行き（電子工学業） */}
      <TaiwanPmiOutlookChart
        data={dashboardData?.taiwan_pmi_outlook ?? null}
      />

      {/* コンテナ運賃指数（SCFI / CCFI） */}
      <ChinaShanghaiContainerFreightIndexChart
        data={dashboardData?.china_shanghai_container_freight_index ?? null}
      />

      {/* バルチック海運指数（BDI） */}
      <BalticDryIndexChart />
    </div>
  )
}
