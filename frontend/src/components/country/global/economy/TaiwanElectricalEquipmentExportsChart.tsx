/**
 * 台湾電気機器輸出チャートコンポーネント
 *
 * データ:
 * - value: 前年比 YoY (%)
 * - mom: 前月比 MoM (%)
 * - raw_value: 原数値（百萬美元）
 *
 * データソース:
 * - MOF (Ministry of Finance, Taiwan)
 * - MajExシート (1)電子零組件
 *
 * 注意:
 * - 毎月7~12日の16:00 UTC+8に更新
 * - FMPマッピングなし（マーケットインパクトタブなし）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

import type { TaiwanElectricalEquipmentExportsData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface TaiwanElectricalEquipmentExportsChartProps {
  data: TaiwanElectricalEquipmentExportsData | null
}

interface ChartDataPoint {
  date: string
  yoy: number | null
  mom: number | null
  [key: string]: unknown
}

type DataKind = 'yoy' | 'mom'
type DisplayMode = 'chart' | 'heatmap'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

const COLORS = {
  yoy: '#7C3AED',
  mom: '#0891B2',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function TaiwanElectricalEquipmentExportsChart({ data }: TaiwanElectricalEquipmentExportsChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 'default',
    mom: 3,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []
    return data.data
      .filter(d => d.value !== null || d.mom !== null)
      .map(d => ({
        date: d.date,
        yoy: d.value,
        mom: d.mom,
      }))
  }, [data])

  const chartData = useSortedData(rawChartData)

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  // ヒートマップ用データ
  const momTableData = useMonthlyTableData(chartData, (item: ChartDataPoint) => item.mom)

  const hasData = chartData.length > 0

  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="台湾電気機器輸出" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="台湾電気機器輸出" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="taiwan-electronics-exports">
      <ChartContainer
        title="台湾電気機器輸出（電子零組件）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="MOF (Ministry of Finance, Taiwan)"
        sourceUrl="https://www.mof.gov.tw/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={dataKind === 'yoy' ? latest?.yoy : latest?.mom}
          valueColor={dataKind === 'yoy' ? COLORS.yoy : COLORS.mom}
          date={latest?.date}
          format="percent"
        />

        {/* 上段: 指標種別 + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=taiwan_electrical_equipment_exports', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 下段: 表示形式（前月比のときのみ） */}
        {dataKind === 'mom' && (
          <div style={{ marginBottom: 8 }}>
            <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
          </div>
        )}

        {/* 期間セレクター */}
        {(dataKind === 'yoy' || (dataKind === 'mom' && displayMode === 'chart')) && (
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
        )}

        {/* ヒートマップ */}
        {dataKind === 'mom' && displayMode === 'heatmap' && <MonthlyTable data={momTableData} />}

        {/* 前年比グラフ（折れ線） */}
        {dataKind === 'yoy' && (
          <StandardLineChart
            data={filteredData}
            lines={[
              { dataKey: 'yoy', color: COLORS.yoy, name: '台湾電気機器輸出（前年比）' },
            ]}
            yAxisFormatter={(v) => `${v}%`}
            tooltipValueFormatter={(v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : 'N/A'}
            yDomain={['dataMin - 5', 'dataMax + 5']}
            showZeroLine={true}
          />
        )}

        {/* 前月比グラフ（棒グラフ） */}
        {dataKind === 'mom' && displayMode === 'chart' && (
          <StandardBarChart
            data={filteredData}
            bars={[
              { dataKey: 'mom', color: COLORS.mom, name: '台湾電気機器輸出（前月比）' },
            ]}
            yAxisFormatter={(v) => `${v}%`}
            tooltipValueFormatter={(v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : 'N/A'}
            yDomain={['dataMin - 3', 'dataMax + 3']}
          />
        )}
      </ChartContainer>
    </div>
  )
}
