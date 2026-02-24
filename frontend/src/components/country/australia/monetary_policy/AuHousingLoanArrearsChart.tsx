/**
 * オーストラリア 住宅ローン延滞率チャートコンポーネント
 *
 * 30-89日延滞率、不良債権率（90日以上）、合計延滞率の3系列を表示
 *
 * データソース:
 * - APRA Quarterly ADI Property Exposures Statistics
 *
 * 発表スケジュール:
 * - 四半期（2/5/8/11月頃）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { AuHousingLoanArrearsData } from '../../../../hooks/useDashboardData'

import { LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'
import {
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// カラー設定
const COLORS = {
  past_due_30_89: '#E67E22',  // オレンジ - 30-89日延滞
  non_performing: '#E74C3C',  // 赤 - 不良債権(90日+)
  total_arrears: '#8E44AD',   // 紫 - 合計延滞
}

interface AuHousingLoanArrearsChartProps {
  data: AuHousingLoanArrearsData | null
}

export default function AuHousingLoanArrearsChart({ data }: AuHousingLoanArrearsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const chartData = useMemo(() => {
    if (!data?.data) return []
    return [...data.data].sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2019,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="住宅ローン延滞率（オーストラリア）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="住宅ローン延滞率（オーストラリア）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="au-housing-loan-arrears-chart">
      <ChartContainer
        title="住宅ローン延滞率"
        showPeriodSelector={false}
        dataSource="APRA"
        sourceUrl="https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-statistics"
      >
        {/* 最新値表示（3系列） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 30-89日延滞 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.past_due_30_89,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>30-89日延滞</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.past_due_30_89 }}>
              {latest?.past_due_30_89 != null ? `${latest.past_due_30_89.toFixed(2)}%` : '-'}
            </span>
          </div>

          {/* 不良債権(90日+) */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.non_performing,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>不良債権(90日+)</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.non_performing }}>
              {latest?.non_performing != null ? `${latest.non_performing.toFixed(2)}%` : '-'}
            </span>
          </div>

          {/* 合計延滞 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.total_arrears,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>合計延滞</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.total_arrears }}>
              {latest?.total_arrears != null ? `${latest.total_arrears.toFixed(2)}%` : '-'}
            </span>
          </div>

          {/* 日付・次回発表情報 */}
          <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-end', fontSize: 11, color: '#8c8c8c' }}>
            {latest?.date && <div>{latest.date}</div>}
            {data.next_release && (
              <div>
                次回発表: {(data.next_release as { date: string; label?: string }).date}
                {(data.next_release as { date: string; label?: string }).label && ` - ${(data.next_release as { date: string; label?: string }).label}`}
              </div>
            )}
          </div>
        </div>

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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=au_housing_loan_arrears', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'past_due_30_89', color: COLORS.past_due_30_89, name: '30-89日延滞', hide: hiddenSeries.has('past_due_30_89') },
                      { dataKey: 'non_performing', color: COLORS.non_performing, name: '不良債権(90日+)', hide: hiddenSeries.has('non_performing') },
                      { dataKey: 'total_arrears', color: COLORS.total_arrears, name: '合計延滞', hide: hiddenSeries.has('total_arrears') },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    yDomain={['dataMin - 0.1', 'dataMax + 0.1']}
                    tooltipValueFormatter={(v) => `${v.toFixed(3)}%`}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
