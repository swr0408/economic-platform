/**
 * 中国 集積回路生産チャートコンポーネント
 *
 * 3系列:
 * - raw_value: 当期生産量（億個）
 * - yoy: 前年比成長率(%)
 * - mom: 前月比(%)
 *
 * データソース: NBS（国家統計局）
 * 工业主要产品产量 → 集成电路
 *
 * FMPマッピング: なし（マーケットインパクトタブなし）
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

import type { CnIntegratedCircuitManufacturingData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface Props {
  data: CnIntegratedCircuitManufacturingData | null
}

interface ChartDataPoint {
  date: string
  raw_value: number | null
  yoy: number | null
  mom: number | null
  [key: string]: unknown
}

type DataKind = 'raw_value' | 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'raw_value', label: '原数値' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

const COLORS = {
  raw_value: '#1E88E5',
  yoy: '#7C3AED',
  mom: '#0891B2',
}

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnIntegratedCircuitManufacturingChart({ data }: Props) {
  const [dataKind, setDataKind] = useState<DataKind>('raw_value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    raw_value: 10 as PeriodType,
    yoy: 10 as PeriodType,
    mom: 3 as PeriodType,
  })

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []
    return data.data
      .filter(item => item.raw_value != null || item.yoy != null)
      .map(item => ({
        date: item.date,
        raw_value: item.raw_value,
        yoy: item.yoy,
        mom: item.mom,
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
      <div id="cn-integrated-circuit-manufacturing">
        <LoadingChart title="集積回路生産" />
      </div>
    )
  }

  if (!hasData) {
    return (
      <div id="cn-integrated-circuit-manufacturing">
        <ChartContainer title="集積回路生産" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = data.latest

  const getLatestValueInfo = () => {
    if (dataKind === 'raw_value') {
      return {
        label: '集積回路生産（当期）',
        value: latest?.raw_value,
        color: COLORS.raw_value,
        format: 'number' as const,
        unit: '億個',
        decimals: 1,
      }
    }
    if (dataKind === 'yoy') {
      return {
        label: '前年比',
        value: latest?.yoy,
        color: COLORS.yoy,
        format: 'percent' as const,
        unit: '%',
        decimals: 1,
      }
    }
    return {
      label: '前月比',
      value: latest?.mom,
      color: COLORS.mom,
      format: 'percent' as const,
      unit: '%',
      decimals: 1,
    }
  }

  const latestInfo = getLatestValueInfo()

  return (
    <div id="cn-integrated-circuit-manufacturing">
      <ChartContainer
        title="集積回路生産"
        showPeriodSelector={false}
        dataSource="NBS（国家統計局）"
        sourceUrl="https://data.stats.gov.cn/english/easyquery.htm?cn=A01"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={latestInfo.label}
          value={latestInfo.value}
          valueColor={latestInfo.color}
          date={latest?.date}
          format={latestInfo.format}
          unit={latestInfo.unit}
          decimals={latestInfo.decimals}
          dateFormatter={formatDateFull}
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
              onClick={() => window.open('/compare?s=china_integrated_circuit_manufacturing', '_blank')}
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

        {/* 原数値グラフ（折れ線） */}
        {dataKind === 'raw_value' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'raw_value', color: COLORS.raw_value, name: '集積回路生産（億個）' },
              ]}
              yAxisFormatter={(v) => `${v.toFixed(0)}`}
              xAxisFormatter={formatDateLabel}
              tooltipLabelFormatter={formatDateFull}
              tooltipValueFormatter={(v) => v != null ? `${v.toFixed(1)}億個` : 'N/A'}
              showLegend={false}
              yDomain={['dataMin - 20', 'dataMax + 20']}
            />
          </>
        )}

        {/* 前年比グラフ（折れ線） */}
        {dataKind === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'yoy', color: COLORS.yoy, name: '集積回路生産（前年比）' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              xAxisFormatter={formatDateLabel}
              tooltipLabelFormatter={formatDateFull}
              yDomain={['dataMin - 2', 'dataMax + 2']}
              tooltipValueFormatter={(v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : 'N/A'}
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

        {/* 前月比チャート（棒グラフ） */}
        {dataKind === 'mom' && displayMode === 'chart' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardBarChart
              data={filteredData}
              bars={[
                { dataKey: 'mom', color: COLORS.mom, name: '集積回路生産（前月比）' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 5', 'dataMax + 5']}
              tooltipValueFormatter={(v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : 'N/A'}
            />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
