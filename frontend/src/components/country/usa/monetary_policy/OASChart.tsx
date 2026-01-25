/**
 * OAS（Option-Adjusted Spread）チャートコンポーネント
 *
 * 3つのシリーズをボタンで切り替え:
 * - BAMLH0A0HYM2: ICE BofA US High Yield Index OAS
 * - BAMLC0A0CM: ICE BofA US Corporate Index OAS
 * - BAMLH0A0HYM2EY: ICE BofA US High Yield Index Effective Yield
 *
 * 日次データ（毎日9:00 AM CST発表）
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip, Radio } from 'antd'
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
interface OASItem {
  date: string
  value: number
}

interface OASData {
  hy_spread: OASItem[]
  ig_spread: OASItem[]
  hy_yield: OASItem[]
}

interface OASChartProps {
  data: OASData | null
}

interface OASChartData {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

type SeriesType = 'hy_spread' | 'ig_spread' | 'hy_yield'

const SERIES_CONFIG: Record<SeriesType, { label: string; name: string; color: string; unit: string }> = {
  hy_spread: {
    label: 'High Yield OAS',
    name: 'ICE BofA US High Yield Index OAS',
    color: CHART_COLORS.red,
    unit: '%',
  },
  ig_spread: {
    label: 'IG OAS',
    name: 'ICE BofA US Corporate Index OAS',
    color: CHART_COLORS.primary,
    unit: '%',
  },
  hy_yield: {
    label: 'HY Effective Yield',
    name: 'ICE BofA US High Yield Index Effective Yield',
    color: CHART_COLORS.orange,
    unit: '%',
  },
}

export default function OASChart({ data }: OASChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [selectedSeries, setSelectedSeries] = useState<SeriesType>('hy_spread')

  // 選択されたシリーズのデータを取得
  const chartData = useMemo<OASChartData[]>(() => {
    if (!data) return []

    const seriesData = data[selectedSeries]
    if (!seriesData || seriesData.length === 0) return []

    const result: OASChartData[] = seriesData.map((item) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data, selectedSeries])

  // 値フォーマット
  const formatValue = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  // Y軸フォーマット
  const formatYAxis = (value: number) => {
    return `${value.toFixed(1)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2008,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // 現在のシリーズ設定
  const currentConfig = SERIES_CONFIG[selectedSeries]

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="OAS（Option-Adjusted Spread）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="OAS（Option-Adjusted Spread）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="oas-chart">
      <ChartContainer
        title="OAS（Option-Adjusted Spread）"
        showPeriodSelector={false}
        dataSource="FRED"
        sourceUrl="https://fred.stlouisfed.org/series/BAMLH0A0HYM2"
      >
        {/* シリーズ切り替えボタン */}
        <div style={{ marginBottom: 16 }}>
          <Radio.Group
            value={selectedSeries}
            onChange={(e) => setSelectedSeries(e.target.value)}
            buttonStyle="solid"
            size="middle"
          >
            <Radio.Button value="hy_spread">ハイイールド債OAS(High Yield OAS)</Radio.Button>
            <Radio.Button value="ig_spread">投資適格社債OAS(IG OAS)</Radio.Button>
            <Radio.Button value="hy_yield">ハイイールド債実効利回り(HY Effective Yield)</Radio.Button>
          </Radio.Group>
        </div>

        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={currentConfig.label}
          value={latestValue ? formatValue(latestValue.value) : null}
          valueColor={currentConfig.color}
          date={latestValue?.date}
          format="raw"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=oas_hy_spread&s=oas_ig_spread', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={currentConfig.color}
          name={currentConfig.name}
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
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
                            backgroundColor: item.color || currentConfig.color,
                            marginRight: 6,
                          }}
                        />
                        {currentConfig.label}
                      </span>
                      <span style={{ fontWeight: 500, color: item.color || currentConfig.color }}>
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
