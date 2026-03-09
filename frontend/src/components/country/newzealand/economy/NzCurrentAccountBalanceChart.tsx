/**
 * NZ 経常収支（Current Account Balance）チャートコンポーネント
 *
 * データ:
 * - value:      経常収支（十億NZD）
 * - qoq_change: 前期増減幅（十億NZD）
 *
 * データソース:
 * - Stats NZ Balance of Payments and International Investment Position
 * - https://www.stats.govt.nz/
 *
 * FMPマッピング:
 * - Current Account (econalpha_id: nz_current_account_balance)
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
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
  StandardBarChart,
  ViewModeButtonGroup,
  LatestValueBox,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzCurrentAccountBalanceData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface NzCurrentAccountBalanceChartProps {
  data: NzCurrentAccountBalanceData | null
}

type ViewMode = 'value' | 'qoq'

// カラー設定
const COLOR_POSITIVE = '#16a34a'   // 黒字（正）
const COLOR_NEGATIVE = '#dc2626'   // 赤字（負）
const COLOR_VALUE = '#0ea5e9'      // 経常収支（折れ線）
const COLOR_QOQ = '#f59e0b'        // 前期増減幅

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}/Q${quarter}`
}

const formatQuarterLabelJP = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}年 Q${quarter}`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NzCurrentAccountBalanceChart({ data }: NzCurrentAccountBalanceChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('value')

  // ビューモードごとに期間を別管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 20,
    qoq: 20,
  })

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data ?? [])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="経常収支" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="経常収支" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]
  const value = latest?.value ?? null
  const qoqChange = latest?.qoq_change ?? null

  return (
    <div id="nz-current-account-balance">
      <ChartContainer
        title="経常収支"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/information-releases/?filters=Balance%20of%20payments"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '経常収支',
              value: value,
              color: value !== null && value >= 0 ? COLOR_POSITIVE : COLOR_NEGATIVE,
              format: 'number',
              decimals: 3,
              unit: '十億NZD',
            },
            {
              label: '前期増減幅',
              value: qoqChange,
              color: qoqChange !== null && qoqChange >= 0 ? COLOR_POSITIVE : COLOR_NEGATIVE,
              format: 'number',
              decimals: 3,
              unit: '十億NZD',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatQuarterLabelJP}
          nextRelease={data?.next_release ? { date: data.next_release.date } : undefined}
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
                  {/* 上段: ビューモード切替 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={[
                        { mode: 'value', label: '経常収支' },
                        { mode: 'qoq', label: '前期増減幅' },
                      ]}
                      currentMode={viewMode}
                      onChange={(mode) => setViewMode(mode as ViewMode)}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_current_account_balance', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* 経常収支: 棒グラフ */}
                  {viewMode === 'value' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'value', color: COLOR_VALUE, name: '経常収支' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                      xAxisFormatter={formatQuarterLabel}
                      tooltipLabelFormatter={formatQuarterLabelJP}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(3)}十億NZD`}
                    />
                  )}

                  {/* 前期増減幅: 棒グラフ */}
                  {viewMode === 'qoq' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'qoq_change', color: COLOR_QOQ, name: '前期増減幅' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                      xAxisFormatter={formatQuarterLabel}
                      tooltipLabelFormatter={formatQuarterLabelJP}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(3)}十億NZD`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_current_account_balance" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
