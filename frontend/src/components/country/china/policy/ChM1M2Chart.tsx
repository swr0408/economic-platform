/**
 * China M1/M2 貨幣供応量チャートコンポーネント
 *
 * データ項目:
 * - m2: M2残高（億元）前年比（%）
 * - m1: M1残高（億元）前年比（%）
 *
 * 表示モード:
 * - 前年比（YoY）: M2/M1 前年比（折れ線グラフ）+ ヒートマップ
 * - 残高（Level）: M2/M1 水準値 → 兆元換算（折れ線グラフ）
 *
 * データソース: 中国人民銀行（PBOC）
 * https://camlmac.pbc.gov.cn/diaochatongjisi/116219/116319/index.html
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { ChM1M2Data } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface ChM1M2ChartProps {
  data: ChM1M2Data | null
}

type ViewMode = 'yoy' | 'level'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy',   label: '前年比' },
  { mode: 'level', label: '残高' },
]

const COLOR_M2 = '#3b82f6'  // 青
const COLOR_M1 = '#ef4444'  // 赤

// =============================================================================
// 日付フォーマット
// =============================================================================

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

export default function ChM1M2Chart({ data }: ChM1M2ChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(
    viewMode,
    { yoy: 10, level: 10 }
  )

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="M1/M2（貨幣供応量）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="M1/M2（貨幣供応量）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]
  // 億元 → 兆元換算（÷10000）
  const latestM2Trillion = latest?.m2 != null ? latest.m2 / 10000 : null
  const latestM1Trillion = latest?.m1 != null ? latest.m1 / 10000 : null

  // 最新値表示アイテム
  const latestItems =
    viewMode === 'yoy'
      ? [
          {
            label: 'M2 前年比',
            value: latest?.m2_yoy ?? null,
            color: COLOR_M2,
            unit: '%',
            decimals: 1,
          },
          {
            label: 'M1 前年比',
            value: latest?.m1_yoy ?? null,
            color: COLOR_M1,
            unit: '%',
            decimals: 1,
          },
        ]
      : [
          {
            label: 'M2',
            value: latestM2Trillion,
            color: COLOR_M2,
            unit: '兆元',
            decimals: 1,
          },
          {
            label: 'M1',
            value: latestM1Trillion,
            color: COLOR_M1,
            unit: '兆元',
            decimals: 1,
          },
        ]

  // グラフ用データ（兆元換算）
  const chartData = filteredData.map(d => ({
    ...d,
    m2_trillion: d.m2 != null ? d.m2 / 10000 : null,
    m1_trillion: d.m1 != null ? d.m1 / 10000 : null,
  }))

  // 前年比グラフライン（M1は右Y軸）
  const yoyLines = [
    { dataKey: 'm2_yoy', color: COLOR_M2, name: 'M2', yAxisId: 'left' as const },
    { dataKey: 'm1_yoy', color: COLOR_M1, name: 'M1', yAxisId: 'right' as const },
  ]

  // 残高グラフライン（M1は右Y軸）
  const levelLines = [
    { dataKey: 'm2_trillion', color: COLOR_M2, name: 'M2（兆元）', yAxisId: 'left' as const },
    { dataKey: 'm1_trillion', color: COLOR_M1, name: 'M1（兆元）', yAxisId: 'right' as const },
  ]

  return (
    <div id="m1-m2">
      <ChartContainer
        title="M1/M2（貨幣供応量）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国人民銀行（PBOC）"
        sourceUrl="https://camlmac.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latest?.date}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ?? null}
        />

        {/* ビューモード切替 + データ比較ボタン（同一行） */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup
            options={VIEW_MODE_OPTIONS}
            currentMode={viewMode}
            onChange={setViewMode}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ch_m2_yoy&s=ch_m1_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* 前年比チャート */}
        {viewMode === 'yoy' && (
          <StandardLineChart
            data={filteredData}
            lines={yoyLines}
            yAxisFormatter={(v) => `${v.toFixed(1)}%`}
            yDomain={['dataMin - 1', 'dataMax + 1']}
            rightYAxisFormatter={(v) => `${v.toFixed(1)}%`}
            rightYDomain={['dataMin - 1', 'dataMax + 1']}
            xAxisFormatter={formatDateLabel}
            tooltipLabelFormatter={formatDateFull}
            tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
            showZeroLine={true}
            showLegend={true}
          />
        )}

        {/* 残高チャート（兆元） */}
        {viewMode === 'level' && (
          <StandardLineChart
            data={chartData}
            lines={levelLines}
            yAxisFormatter={(v) => `${v.toFixed(0)}兆`}
            yDomain={['dataMin - 5', 'dataMax + 5']}
            rightYAxisFormatter={(v) => `${v.toFixed(0)}兆`}
            rightYDomain={['dataMin - 5', 'dataMax + 5']}
            xAxisFormatter={formatDateLabel}
            tooltipLabelFormatter={formatDateFull}
            tooltipValueFormatter={(v) => `${v.toFixed(1)} 兆元`}
            showZeroLine={false}
            showLegend={true}
          />
        )}
      </ChartContainer>
    </div>
  )
}
