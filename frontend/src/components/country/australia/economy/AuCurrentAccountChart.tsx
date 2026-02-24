/**
 * オーストラリア経常収支チャートコンポーネント
 *
 * ABS 5302.0 Table 4: Current Account, Seasonally Adjusted
 * Series ID: A3535187L
 *
 * データソース:
 * - Australian Bureau of Statistics (ABS)
 * - FMP Economic Calendar（次回発表日）
 *
 * 発表スケジュール:
 * - 四半期（約Q+3ヶ月後）
 *
 * 単位:
 * - B AUD（十億豪ドル）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useQuarterlyTableData,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuCurrentAccountData } from '../../../../hooks/useDashboardData'

interface AuCurrentAccountChartProps {
  data: AuCurrentAccountData | null
}

interface ChartDataPoint {
  date: string
  value: number
  qoq_diff: number | null
  yoy_diff: number | null
  [key: string]: unknown
}

type ViewMode = 'value' | 'qoq_chart' | 'yoy_chart' | 'qoq_table'

const COLORS = {
  value: '#1890ff',
  qoq: '#52c41a',
  yoy: '#fa8c16',
}

export default function AuCurrentAccountChart({ data }: AuCurrentAccountChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default' as PeriodType,
    qoq_chart: 3 as PeriodType,
    yoy_chart: 3 as PeriodType,
    qoq_table: 'default' as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    const qoqMap = new Map<string, number>()
    if (data.qoq_diff) {
      data.qoq_diff.forEach(item => {
        qoqMap.set(item.date, item.value)
      })
    }

    const yoyMap = new Map<string, number>()
    if (data.yoy_diff) {
      data.yoy_diff.forEach(item => {
        yoyMap.set(item.date, item.value)
      })
    }

    return data.data
      .map(item => ({
        date: item.date,
        value: item.value,
        qoq_diff: qoqMap.get(item.date) ?? null,
        yoy_diff: yoyMap.get(item.date) ?? null,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×四半期別のマトリックス）
  const tableData = useQuarterlyTableData(
    chartData,
    (item) => item.qoq_diff,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 現在の表示値
  const currentValue = useMemo(() => {
    if (!latest) return null
    if (viewMode === 'value') return latest.value
    if (viewMode === 'yoy_chart') return latest.yoy_diff
    return latest.qoq_diff
  }, [latest, viewMode])

  const currentColor = viewMode === 'value' ? COLORS.value : viewMode === 'yoy_chart' ? COLORS.yoy : COLORS.qoq

  if (data === null) {
    return <LoadingChart title="経常収支（オーストラリア）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="経常収支（オーストラリア）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const getLabel = () => {
    if (viewMode === 'value') return '経常収支'
    if (viewMode === 'yoy_chart') return '前年同期差分'
    return '前期差分'
  }

  return (
    <div id="au-current-account-chart">
      <ChartContainer
        title="経常収支"
        showPeriodSelector={false}
        dataSource="ABS"
        sourceUrl="https://www.abs.gov.au/statistics/economy/international-trade/balance-payments-and-international-investment-position-australia/latest-release"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getLabel()}
          value={currentValue != null ? `AUD ${currentValue >= 0 ? '+' : ''}${currentValue.toFixed(2)}B` : null}
          valueColor={currentColor}
          date={latest?.date}
          nextRelease={data.next_release ?? undefined}
          format="raw"
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode)}
                    options={[
                      { mode: 'value', label: '原数値' },
                      { mode: 'qoq_chart', label: '前期差分' },
                      { mode: 'yoy_chart', label: '前年同期差分' },
                      { mode: 'qoq_table', label: '前期差分（テーブル）' },
                    ]}
                  />

                  {/* 期間セレクター */}
                  {(viewMode === 'value' || viewMode === 'qoq_chart' || viewMode === 'yoy_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=au_current_account', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'qoq_table' && (
                    <QuarterlyTable
                      data={tableData}
                      decimals={2}
                      showLegend={false}
                      helperText="※ 直近10年間の前期差分データ（単位: B AUD）"
                    />
                  )}

                  {viewMode === 'value' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: 'value',
                          color: COLORS.value,
                          name: '経常収支（B AUD）',
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `AUD ${v >= 0 ? '+' : ''}${v.toFixed(2)}B`}
                    />
                  )}

                  {viewMode === 'qoq_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: 'qoq_diff',
                          color: COLORS.qoq,
                          name: '前期差分（B AUD）',
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `AUD ${v >= 0 ? '+' : ''}${v.toFixed(2)}B`}
                    />
                  )}

                  {viewMode === 'yoy_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: 'yoy_diff',
                          color: COLORS.yoy,
                          name: '前年同期差分（B AUD）',
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `AUD ${v >= 0 ? '+' : ''}${v.toFixed(2)}B`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_current_account" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
