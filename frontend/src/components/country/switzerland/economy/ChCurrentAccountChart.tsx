/**
 * スイス経常収支チャートコンポーネント
 *
 * SNB Data Portal: bopoverq cube (Balance of payments overview, quarterly)
 * 経常収支ネット（受取−支払）
 *
 * データソース:
 * - Swiss National Bank (SNB Data Portal)
 * - FMP Economic Calendar（最新値の先行取得）
 *
 * 発表スケジュール:
 * - 四半期（約Q+3ヶ月後）
 *
 * 単位:
 * - B CHF（十億スイスフラン）
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

import type { CHCurrentAccountData } from '../../../../hooks/useDashboardData'

interface ChCurrentAccountChartProps {
  data: CHCurrentAccountData | null
}

interface ChartDataPoint {
  date: string
  value: number
  qoq_change: number | null
  [key: string]: unknown
}

type ViewMode = 'value' | 'qoq_chart' | 'qoq_table'

const COLORS = {
  value: '#1890ff',
  qoq: '#52c41a',
}

export default function ChCurrentAccountChart({ data }: ChCurrentAccountChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default' as PeriodType,
    qoq_chart: 3 as PeriodType,
    qoq_table: 'default' as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    // QoQ changeをMapに
    const qoqMap = new Map<string, number>()
    if (data.qoq_change) {
      data.qoq_change.forEach(item => {
        qoqMap.set(item.date, item.value)
      })
    }

    return data.data
      .map(item => ({
        date: item.date,
        value: item.value,
        qoq_change: qoqMap.get(item.date) ?? null,
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
    (item) => viewMode === 'qoq_table' ? item.qoq_change : item.value,
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
    return viewMode === 'value' ? latest.value : latest.qoq_change
  }, [latest, viewMode])

  const currentColor = viewMode === 'value' ? COLORS.value : COLORS.qoq

  if (data === null) {
    return <LoadingChart title="経常収支（スイス）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="経常収支（スイス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-current-account-chart">
      <ChartContainer
        title="経常収支"
        showPeriodSelector={false}
        dataSource="SNB"
        sourceUrl="https://data.snb.ch/en/topics/aube"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={viewMode === 'value' ? '経常収支' : '前期増減幅'}
          value={currentValue != null ? `CHF ${currentValue >= 0 ? '+' : ''}${currentValue.toFixed(2)}B` : null}
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
                      { mode: 'qoq_chart', label: '前期増減幅' },
                      { mode: 'qoq_table', label: '前期増減幅（テーブル）' },
                    ]}
                  />

                  {/* 期間セレクター */}
                  {(viewMode === 'value' || viewMode === 'qoq_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=ch_current_account', '_blank')}
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
                      helperText="※ 直近10年間の前期増減幅データ（単位: B CHF）"
                    />
                  )}

                  {viewMode === 'value' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: 'value',
                          color: COLORS.value,
                          name: '経常収支（B CHF）',
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `CHF ${v >= 0 ? '+' : ''}${v.toFixed(2)}B`}
                    />
                  )}

                  {viewMode === 'qoq_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: 'qoq_change',
                          color: COLORS.qoq,
                          name: '前期増減幅（B CHF）',
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `CHF ${v >= 0 ? '+' : ''}${v.toFixed(2)}B`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ch_current_account" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
