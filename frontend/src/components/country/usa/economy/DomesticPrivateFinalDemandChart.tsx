import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import { usePeriodFiltering, formatQuarterLabel, formatPercent, type PeriodType } from '../common/useChartData'
import { NoDataMessage, StandardLineChart } from '../common/ChartComponents'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

interface DomesticPrivateFinalDemandItem {
  date: string
  quarter: string
  ex_sw_pc: number | null
  standard: number | null
}

interface DomesticPrivateFinalDemandChartProps {
  data: DomesticPrivateFinalDemandItem[] | null
}

const COLOR_EX = '#fa541c'        // 除くSW・PC（メイン、独自推計）
const COLOR_STANDARD = '#1890ff'  // 標準（参考）

const LINES = [
  { dataKey: 'ex_sw_pc', color: COLOR_EX, name: '除くSW・PC投資（独自推計）', strokeWidth: 2 },
  { dataKey: 'standard', color: COLOR_STANDARD, name: '国内民間最終需要（標準）', strokeWidth: 1.5, strokeDasharray: '5 3' },
]

export default function DomesticPrivateFinalDemandChart({ data }: DomesticPrivateFinalDemandChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(20)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return []
    return [...data].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  if (data === null) {
    return <LoadingChart title="国内民間最終需要（除くSW・PC投資）" />
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="国内民間最終需要（除くSW・PC投資）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = chartData[chartData.length - 1]
  const diff = latest.ex_sw_pc !== null && latest.standard !== null
    ? latest.ex_sw_pc - latest.standard
    : null

  return (
    <div id="domestic-private-final-demand-chart">
      <ChartContainer
        title="国内民間最終需要 / 除くソフトウェア・コンピューター設備投資"
        showPeriodSelector={false}
        dataSource="BEA"
        sourceUrl="https://www.bea.gov/data/gdp/gross-domestic-product"
      >
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ marginBottom: 4, width: '100%' }}>
            <span style={{ fontSize: 12, fontWeight: 500, color: TEXT_COLORS.secondary }}>
              最新: {latest.quarter}（前期比年率）
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, fontSize: 11, width: '100%' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '4px 8px',
                background: 'rgba(255,255,255,0.05)',
                borderRadius: 4,
                borderLeft: `3px solid ${COLOR_EX}`,
              }}
            >
              <span style={{ color: TEXT_COLORS.secondary }}>除くSW・PC（独自推計）</span>
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: latest.ex_sw_pc !== null && latest.ex_sw_pc >= 0 ? '#52c41a' : '#ff4d4f',
                }}
              >
                {formatPercent(latest.ex_sw_pc)}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '4px 8px',
                background: 'rgba(255,255,255,0.05)',
                borderRadius: 4,
                borderLeft: `3px solid ${COLOR_STANDARD}`,
              }}
            >
              <span style={{ color: TEXT_COLORS.secondary }}>標準（参考）</span>
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: latest.standard !== null && latest.standard >= 0 ? '#52c41a' : '#ff4d4f',
                }}
              >
                {formatPercent(latest.standard)}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '4px 8px',
                background: 'rgba(255,255,255,0.05)',
                borderRadius: 4,
                borderLeft: `3px solid ${TEXT_COLORS.tertiary}`,
              }}
            >
              <span style={{ color: TEXT_COLORS.secondary }}>差分 (除く - 標準)</span>
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: diff !== null && diff >= 0 ? '#52c41a' : '#ff4d4f',
                }}
              >
                {diff !== null ? `${diff >= 0 ? '+' : ''}${diff.toFixed(2)}%pt` : 'N/A'}
              </span>
            </div>
          </div>
        </div>

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
                        onClick={() =>
                          window.open(
                            '/compare?s=domestic_private_final_demand_excluding_software_and_computer_equipment_investment',
                            '_blank',
                          )
                        }
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={LINES}
                    height={450}
                    xAxisFormatter={formatQuarterLabel}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    tooltipLabelFormatter={formatQuarterLabel}
                    tooltipValueFormatter={(v) => (v != null ? `${v.toFixed(2)}%` : 'N/A')}
                    showZeroLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="gdp_growth" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
