/**
 * オーストラリア アンダー・ユーティライゼーション チャートコンポーネント
 *
 * 不完全利用率、不完全雇用率、失業率の3系列を表示
 *
 * データソース:
 * - ABS 6202.0 Labour Force, Table 23
 *
 * 発表スケジュール:
 * - 毎月（通常第3木曜日、Labour Force Survey）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { AuUnderutilizationData } from '../../../../hooks/useDashboardData'

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

import MarketImpactTab from '../../../indicator/MarketImpactTab'

// カラー設定
const COLORS = {
  underutilisation: '#E74C3C',  // 赤
  underemployment: '#E67E22',   // オレンジ
  unemployment: '#3498DB',       // 青
}

interface AuUnderutilizationChartProps {
  data: AuUnderutilizationData | null
}

export default function AuUnderutilizationChart({ data }: AuUnderutilizationChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを変換
  const chartData = useMemo(() => {
    if (!data?.data) return []

    return data.data
      .map((item) => ({
        date: item.date,
        underutilisation: item.underutilisation,
        underemployment: item.underemployment,
        unemployment: item.unemployment,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="アンダー・ユーティライゼーション（オーストラリア）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="アンダー・ユーティライゼーション（オーストラリア）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="au-underutilization-chart">
      <ChartContainer
        title="アンダー・ユーティライゼーション"
        showPeriodSelector={false}
        dataSource="ABS"
        sourceUrl="https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/latest-release"
        handbookId="underutilization"
      >
        {/* 最新値表示（3系列） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 不完全利用率 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.underutilisation,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>不完全利用率</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.underutilisation }}>
              {latest?.underutilisation?.toFixed(1) ?? '-'}%
            </span>
          </div>

          {/* 不完全雇用率 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.underemployment,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>不完全雇用率</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.underemployment }}>
              {latest?.underemployment?.toFixed(1) ?? '-'}%
            </span>
          </div>

          {/* 失業率 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.unemployment,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>失業率</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.unemployment }}>
              {latest?.unemployment?.toFixed(1) ?? '-'}%
            </span>
          </div>

          {/* 日付・次回発表情報 */}
          <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-end', fontSize: 11, color: '#8c8c8c' }}>
            {latest?.date && <div>{latest.date}</div>}
            {data.next_release && (
              <div>
                次回発表: {data.next_release.date}{data.next_release.label && ` - ${data.next_release.label}`}
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
                        onClick={() => window.open('/compare?s=au_underutilization', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'underutilisation', color: COLORS.underutilisation, name: '不完全利用率', hide: hiddenSeries.has('underutilisation') },
                      { dataKey: 'underemployment', color: COLORS.underemployment, name: '不完全雇用率', hide: hiddenSeries.has('underemployment') },
                      { dataKey: 'unemployment', color: COLORS.unemployment, name: '失業率', hide: hiddenSeries.has('unemployment') },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_unemployment_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
