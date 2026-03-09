/**
 * 中国 土地売却収入チャートコンポーネント
 *
 * 国有土地使用権出譲収入（累計、亿元）
 * 原数値（累計）/ 前年比 / 前月比（累計差分ベース）
 * 前月比にヒートマップ表示あり
 *
 * FMPマッピング: なし（マーケットインパクトタブなし）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { CHART_COLORS } from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  SimpleLatestValueBox,
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

import type { CnLandSalesIncomeData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface Props {
  data: CnLandSalesIncomeData | null
}

interface ChartDataPoint {
  date: string
  value: number
  yoy: number | null
  mom: number | null
  monthly_increment: number | null
  [key: string]: unknown
}

type DataKind = 'value' | 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'value', label: '原数値' },
  { mode: 'mom', label: '前月比' },
]

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

const COLORS = {
  value: CHART_COLORS.primary,
  yoy: '#DC143C',
  mom: '#2196F3',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnLandSalesIncomeChart({ data }: Props) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 10 as PeriodType,
    yoy: 10 as PeriodType,
    mom: 3 as PeriodType,
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []
    return data.data
      .filter(item => item.value != null)
      .map(item => ({
        date: item.date,
        value: item.value,
        yoy: item.yoy,
        mom: item.mom,
        monthly_increment: item.monthly_increment,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 前月比ヒートマップ用データ
  const momTableData = useMonthlyTableData(sortedData, (item) => (item as ChartDataPoint).mom, 10)

  const hasData = chartData.length > 0

  if (data === null) {
    return (
      <div id="cn-land-sales-income">
        <LoadingChart title="土地売却収入" />
      </div>
    )
  }

  if (!hasData) {
    return (
      <div id="cn-land-sales-income">
        <ChartContainer title="土地売却収入" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = data.latest

  const getSubInfo = () => {
    if (dataKind === 'yoy') {
      return { label: '前年比', value: latest?.yoy }
    }
    if (dataKind === 'mom') {
      return { label: '前月比', value: latest?.mom }
    }
    return { label: undefined, value: undefined }
  }

  const subInfo = getSubInfo()

  return (
    <div id="cn-land-sales-income">
      <ChartContainer
        title="土地売却収入"
        showPeriodSelector={false}
        dataSource="中国財政部"
        sourceUrl="https://gks.mof.gov.cn/tongjishuju/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="土地売却収入（累計）"
          value={latest?.value}
          valueColor={COLORS.value}
          subLabel={subInfo.label}
          subValue={subInfo.value}
          subValueColor={dataKind === 'yoy' ? COLORS.yoy : COLORS.mom}
          date={latest?.date}
          format="number"
          unit="%"
        />

        {/* 上段: 指標種別 + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <ViewModeButtonGroup
            options={DATA_KIND_OPTIONS}
            currentMode={dataKind}
            onChange={setDataKind}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=cn_land_sales_income', '_blank')}
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

        {/* 原数値グラフ */}
        {dataKind === 'value' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'value', color: COLORS.value, name: '土地売却収入（累計）' },
              ]}
              yAxisFormatter={(v) => `${(v / 10000).toFixed(1)}万`}
              tooltipValueFormatter={(v) => `${v.toLocaleString()}亿元`}
              showLegend={false}
            />
          </>
        )}

        {/* 前年比グラフ */}
        {dataKind === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'yoy', color: COLORS.yoy, name: '前年比' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 5', 'dataMax + 5']}
              tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
              showZeroLine={true}
              showLegend={false}
            />
          </>
        )}

        {/* 前月比ヒートマップ */}
        {dataKind === 'mom' && displayMode === 'heatmap' && (
          <MonthlyTable
            data={momTableData}
            showLegend={true}
          />
        )}

        {/* 前月比チャート */}
        {dataKind === 'mom' && displayMode === 'chart' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardBarChart
              data={filteredData}
              bars={[
                { dataKey: 'mom', color: COLORS.mom, name: '前月比' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 10', 'dataMax + 10']}
              tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
            />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
