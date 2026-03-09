/**
 * TGA（財務省一般勘定残高）チャートコンポーネント
 *
 * Treasury General Account (WDTGAL)
 * 週次データ（毎週水曜日発表）
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
interface TGAItem {
  date: string
  value: number
}

interface TGAChartProps {
  data: TGAItem[] | null
}

interface TGAChartData {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

export default function TGAChart({ data }: TGAChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(2)

  // propsのデータをチャート用に変換
  const chartData = useMemo<TGAChartData[]>(() => {
    if (!data || data.length === 0) return []

    const result: TGAChartData[] = data.map((item) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data])

  // 値フォーマット（ミリオンドル単位、ビリオンドル表記）
  const formatValue = (value: number) => {
    // ミリオンドル単位 → ビリオンドルに変換
    const billions = value / 1000
    return `$${billions.toFixed(0)}B`
  }

  // Y軸フォーマット（ビリオンドル表記、簡略版）
  const formatYAxis = (value: number) => {
    const billions = value / 1000
    return `${billions.toFixed(0)}B`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="TGA（財務省一般勘定）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="TGA（財務省一般勘定）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="tga-chart">
      <ChartContainer
        title="TGA（財務省一般勘定）"
        showPeriodSelector={false}
        dataSource="FRB"
        sourceUrl="https://www.federalreserve.gov/releases/h41/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="TGA残高"
          value={latestValue ? formatValue(latestValue.value) : null}
          valueColor={CHART_COLORS.green}
          date={latestValue?.date}
          format="raw"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=tga&s=reserve_balances', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLORS.green}
          name="TGA"
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={['dataMin - 50000', 'dataMax + 50000']}
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
                            backgroundColor: item.color || CHART_COLORS.green,
                            marginRight: 6,
                          }}
                        />
                        {item.name}
                      </span>
                      <span style={{ fontWeight: 500, color: item.color || CHART_COLORS.green }}>
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
