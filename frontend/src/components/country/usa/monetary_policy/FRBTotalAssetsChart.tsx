/**
 * FRB総資産チャートコンポーネント
 *
 * Federal Reserve Balance Sheet (WALCL)
 * 週次データ（毎週木曜日発表）
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
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../common/ChartComponents'
import { CHART_COLORS, DARK_THEME } from '../common/chartConstants'

// Props型定義
interface FRBTotalAssetsItem {
  date: string
  value: number
}

interface FRBTotalAssetsChartProps {
  data: FRBTotalAssetsItem[] | null
}

interface FRBTotalAssetsChartData {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

export default function FRBTotalAssetsChart({ data }: FRBTotalAssetsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(2)

  // propsのデータをチャート用に変換
  const chartData = useMemo<FRBTotalAssetsChartData[]>(() => {
    if (!data || data.length === 0) return []

    const result: FRBTotalAssetsChartData[] = data.map((item) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data])

  // 値フォーマット（億ドル単位、兆ドル表記）
  const formatValue = (value: number) => {
    // WALCL はミリオンドル単位、兆ドルに変換
    const trillions = value / 1000000
    return `$${trillions.toFixed(2)}T`
  }

  // Y軸フォーマット（兆ドル表記、簡略版）
  const formatYAxis = (value: number) => {
    const trillions = value / 1000000
    return `${trillions.toFixed(1)}T`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2008,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="FRB総資産" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="FRB総資産" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="frb-total-assets-chart">
      <ChartContainer
        title="FRB総資産"
        showPeriodSelector={false}
        dataSource="FRB"
        sourceUrl="https://www.federalreserve.gov/releases/h41/"
        handbookId="central-bank-balance-sheet"
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
              onClick={() => window.open('/compare?s=frb_total_assets&s=policy_rate', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLORS.primary}
          name="FRB総資産"
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
                    {formatDateLabel(String(label))}
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
