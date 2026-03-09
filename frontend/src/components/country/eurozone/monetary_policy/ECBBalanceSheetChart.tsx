/**
 * ECBバランスシートチャートコンポーネント
 *
 * ECB Weekly Financial Statements - Total Assets
 * 週次データ（毎週火曜日発表）
 *
 * データソース:
 * - ECB Data Portal (ILM dataset)
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { usePeriodFiltering, formatDateLabel, formatDateLabelFull, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../../usa/common/ChartComponents'
import { CHART_COLORS, DARK_THEME } from '../../usa/common/chartConstants'

import type { ECBBalanceSheetData } from '../../../../hooks/useDashboardData'

interface ECBBalanceSheetChartProps {
  data: ECBBalanceSheetData | null
}

export default function ECBBalanceSheetChart({ data }: ECBBalanceSheetChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)

  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return data.data
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 値フォーマット（百万ユーロ → 兆ユーロ）
  const formatValue = (value: number) => {
    const trillions = value / 1000000
    return `€${trillions.toFixed(2)}T`
  }

  // Y軸フォーマット
  const formatYAxis = (value: number) => {
    const trillions = value / 1000000
    return `${trillions.toFixed(1)}T`
  }

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2008,
  })

  const hasData = chartData.length > 0
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  if (data === null) {
    return <LoadingChart title="ECBバランスシート" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ECBバランスシート" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-balance-sheet-chart">
      <ChartContainer
        title="ECBバランスシート"
        showPeriodSelector={false}
        dataSource="ECB"
        sourceUrl="https://www.ecb.europa.eu/press/pr/wfs/html/index.en.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="総資産残高"
          value={latestValue ? formatValue(latestValue.value) : null}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          format="raw"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ecb_balance_sheet&s=eu_ecb_rate', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLORS.primary}
          name="ECBバランスシート"
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={['dataMin - 100000', 'dataMax + 100000']}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
              return (
                <div
                  style={{
                    backgroundColor: DARK_THEME.bgTertiary,
                    border: `1px solid ${DARK_THEME.borderLight}`,
                    borderRadius: 8,
                    padding: '12px 16px',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                  }}
                >
                  <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
                    {formatDateLabelFull(String(label))}
                  </div>
                  {payload.map((item, index) => (
                    <div
                      key={index}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 4,
                        fontSize: 13,
                      }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            width: 10,
                            height: 10,
                            borderRadius: 2,
                            backgroundColor: item.color || CHART_COLORS.primary,
                            marginRight: 6,
                          }}
                        />
                        {item.name}
                      </span>
                      <span style={{ fontWeight: 500, color: item.color || CHART_COLORS.primary }}>
                        {formatValue(item.value as number)}
                      </span>
                    </div>
                  ))}
                </div>
              )
            }}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
