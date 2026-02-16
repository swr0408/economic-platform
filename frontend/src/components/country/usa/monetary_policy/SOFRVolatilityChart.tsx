/**
 * SOFR ボラティリティチャートコンポーネント
 *
 * NY Fed Markets API から SOFR 履歴を取得し、
 * 20日ローリング標準偏差（ボラティリティ）およびSOFRレートを表示
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
import { NoDataMessage, SimpleLatestValueBox, ViewModeButtonGroup } from '../common/ChartComponents'
import { CHART_COLORS, DARK_THEME } from '../common/chartConstants'
import type { SOFRVolatilityData, SOFRVolatilityItem } from '../../../../hooks/useDashboardData'

// Props型定義
interface SOFRVolatilityChartProps {
  data: SOFRVolatilityData | null
}

interface ChartDataItem {
  date: string
  value: number | null
  volatility_20d: number | null
  sofr: number
  sofr_change: number
  [key: string]: string | number | null | undefined
}

// ビューモード
type ViewMode = 'volatility' | 'sofr'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'volatility', label: 'ボラティリティ' },
  { mode: 'sofr', label: 'SOFR' },
]

export default function SOFRVolatilityChart({ data }: SOFRVolatilityChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [viewMode, setViewMode] = useState<ViewMode>('volatility')

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data || !data.data || data.data.length === 0) return []

    const result: ChartDataItem[] = data.data
      .filter((item: SOFRVolatilityItem) => item.volatility_20d !== null)
      .map((item: SOFRVolatilityItem) => ({
        date: item.date,
        value: viewMode === 'volatility' ? item.volatility_20d : item.sofr,
        volatility_20d: item.volatility_20d,
        sofr: item.sofr,
        sofr_change: item.sofr_change,
      }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data, viewMode])

  // 値フォーマット（bps単位）
  const formatVolatility = (value: number) => {
    return `${value.toFixed(2)} bps`
  }

  // SOFRフォーマット
  const formatSOFR = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  // Y軸フォーマット
  const formatYAxis = (value: number) => {
    if (viewMode === 'volatility') {
      return `${value.toFixed(1)}`
    }
    return `${value.toFixed(2)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="SOFR / ボラティリティ" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="SOFR / ボラティリティ" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 現在のモードに応じた設定
  const currentColor = viewMode === 'volatility' ? CHART_COLORS.purple : CHART_COLORS.primary
  const currentName = viewMode === 'volatility' ? 'SOFR Vol (20d)' : 'SOFR'
  const currentDataKey = viewMode === 'volatility' ? 'volatility_20d' : 'sofr'
  const currentDomain: [number | string, number | string] = viewMode === 'volatility' ? [0, 'auto'] : ['dataMin - 0.5', 'dataMax + 0.5']

  return (
    <div id="sofr-volatility-chart">
      <ChartContainer
        title="SOFR / ボラティリティ"
        showPeriodSelector={false}
        dataSource="NY Fed"
        sourceUrl="https://www.newyorkfed.org/markets/reference-rates/sofr"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={viewMode === 'volatility' ? '20日ボラティリティ' : 'SOFR'}
          value={
            viewMode === 'volatility'
              ? latestValue?.volatility_20d != null
                ? formatVolatility(latestValue.volatility_20d)
                : null
              : latestValue?.sofr != null
                ? formatSOFR(latestValue.sofr)
                : null
          }
          valueColor={currentColor}
          date={latestValue?.date}
          format="raw"
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=sofr_volatility', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey={currentDataKey}
          color={currentColor}
          name={currentName}
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={viewMode === 'volatility'}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={currentDomain}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
              const dataPoint = payload[0]?.payload as ChartDataItem | undefined
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
                    {String(label).replace(/-/g, '/')}
                  </div>
                  <div
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
                          backgroundColor: CHART_COLORS.primary,
                          marginRight: 6,
                        }}
                      />
                      SOFR
                    </span>
                    <span style={{ fontWeight: 500, color: CHART_COLORS.primary }}>
                      {dataPoint?.sofr != null ? formatSOFR(dataPoint.sofr) : 'N/A'}
                    </span>
                  </div>
                  <div
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
                          backgroundColor: CHART_COLORS.purple,
                          marginRight: 6,
                        }}
                      />
                      20日ボラティリティ
                    </span>
                    <span style={{ fontWeight: 500, color: CHART_COLORS.purple }}>
                      {dataPoint?.volatility_20d != null ? formatVolatility(dataPoint.volatility_20d) : 'N/A'}
                    </span>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
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
                          backgroundColor: CHART_COLORS.gray,
                          marginRight: 6,
                        }}
                      />
                      日次変化
                    </span>
                    <span
                      style={{
                        fontWeight: 500,
                        color:
                          dataPoint?.sofr_change != null && dataPoint.sofr_change >= 0
                            ? CHART_COLORS.green
                            : CHART_COLORS.red,
                      }}
                    >
                      {dataPoint?.sofr_change != null
                        ? `${dataPoint.sofr_change >= 0 ? '+' : ''}${dataPoint.sofr_change.toFixed(2)} bps`
                        : 'N/A'}
                    </span>
                  </div>
                </div>
              )
            }}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
