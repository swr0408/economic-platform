/**
 * NZ 経常収支対GDP比（Current Account Balance as % of GDP）チャートコンポーネント
 *
 * データ:
 * - ratio:     経常収支対GDP比（%）、trailing 4四半期合計ベース
 * - ca_value:  経常収支（十億NZD）
 * - gdp_value: GDP（十億NZD）
 *
 * データソース:
 * - Stats NZ Balance of Payments and International Investment Position
 * - Stats NZ GDP Supplementary Tables
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
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
  LatestValueBox,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzCurrentAccountGdpRatioData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface NzCurrentAccountGdpRatioChartProps {
  data: NzCurrentAccountGdpRatioData | null
}

// カラー設定
const COLOR_POSITIVE = '#16a34a'   // 黒字（正）
const COLOR_NEGATIVE = '#dc2626'   // 赤字（負）
const COLOR_RATIO = '#8b5cf6'      // 経常収支対GDP比（紫）

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

export default function NzCurrentAccountGdpRatioChart({ data }: NzCurrentAccountGdpRatioChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(20)

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data ?? [])

  // ratioがnullのデータを除外してからフィルタリング
  const validData = sortedData.filter(d => d.ratio !== null)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(validData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2005,
  })

  const hasData = validData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="経常収支対GDP比" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="経常収支対GDP比" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = validData[validData.length - 1]
  const ratio = latest?.ratio ?? null

  return (
    <div id="nz-current-account-gdp-ratio">
      <ChartContainer
        title="経常収支対GDP比"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/topics/balance-of-payments"
        handbookId="current-account"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '経常収支対GDP比',
              value: ratio,
              color: ratio !== null && ratio >= 0 ? COLOR_POSITIVE : COLOR_NEGATIVE,
              format: 'number',
              decimals: 2,
              unit: '%',
            },
            {
              label: '経常収支',
              value: latest?.ca_value ?? null,
              color: (latest?.ca_value ?? 0) >= 0 ? COLOR_POSITIVE : COLOR_NEGATIVE,
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
                  {/* 期間選択 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_current_account_gdp_ratio', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 経常収支対GDP比: 折れ線グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'ratio', color: COLOR_RATIO, name: '経常収支対GDP比' },
                    ]}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    yDomain={['dataMin - 1', 'dataMax + 1']}
                    xAxisFormatter={formatQuarterLabel}
                    tooltipLabelFormatter={formatQuarterLabelJP}
                    tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                    showZeroLine={true}
                  />
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
