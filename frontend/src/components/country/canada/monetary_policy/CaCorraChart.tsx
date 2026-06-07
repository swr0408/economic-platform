/**
 * CORRA（カナダ翌日物レポ平均金利）チャートコンポーネント
 *
 * Canadian Overnight Repo Rate Average の推移を表示
 *
 * データソース:
 * - Bank of Canada Valet API
 *
 * 発表スケジュール:
 * - 日次（営業日）
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, formatDateLabelFull, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { CaCorraData } from '../../../../hooks/useDashboardData'

interface CaCorraChartProps {
  data: CaCorraData | null
}

interface CaCorraChartData {
  date: string
  value: number
  rate: number
  [key: string]: string | number | null | undefined
}

export default function CaCorraChart({ data }: CaCorraChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(2)

  // propsのデータをチャート用に変換
  const chartData = useMemo<CaCorraChartData[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: CaCorraChartData[] = data.data.map((item) => ({
      date: item.date,
      value: item.value,
      rate: item.value,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data])

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2017,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="CORRA（翌日物レポ平均金利）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CORRA（翌日物レポ平均金利）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ca-corra-chart">
      <ChartContainer
        title="CORRA（翌日物レポ平均金利）"
        showPeriodSelector={false}
        dataSource="Bank of Canada"
        sourceUrl="https://www.bankofcanada.ca/rates/interest-rates/corra/"
        handbookId="ca-corra"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="最新レート"
          value={latestValue?.value}
          valueColor="#10B981"
          date={latestValue?.date}
          format="percent"
          decimals={2}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ca_corra', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>
        <ZoomableChart
          data={filteredData}
          dataKey="rate"
          color="#10B981"
          name="CORRA"
          height={450}
          tickFormatter={formatPercentage}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={['dataMin - 0.5', 'dataMax + 0.5']}
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
                            backgroundColor: item.color || '#10B981',
                            marginRight: 6,
                          }}
                        />
                        {item.name}
                      </span>
                      <span style={{ fontWeight: 500, color: item.color || '#10B981' }}>
                        {formatPercentage(item.value as number)}
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
