/**
 * オーストラリア交易条件チャートコンポーネント
 *
 * ABS 5206.0 Key Aggregates から Terms of Trade を表示
 *
 * データ:
 * - value: Index (Seasonally Adjusted)
 * - qoq: 前期比 (%)
 * - yoy: 前年比 (%)
 *
 * データソース:
 * - ABS (Australian Bureau of Statistics)
 *
 * 発表スケジュール:
 * - 四半期（GDP発表と同時）
 */
import { useState, useMemo, useCallback } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuTermsOfTradeData } from '../../../../hooks/useDashboardData'

interface AuTermsOfTradeChartProps {
  data: AuTermsOfTradeData | null
}

interface ChartDataPoint {
  date: string
  value: number
  qoq: number
  yoy: number
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  tot: '#E67E22',  // オレンジ系
}

// データ種別
type DataKind = 'value' | 'yoy' | 'qoq'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'value', label: '指数' },
  { mode: 'qoq', label: '前期比' },
  { mode: 'yoy', label: '前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// 四半期日付フォーマッター
const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  return dateStr.replace('-', '/')
}

export default function AuTermsOfTradeChart({ data }: AuTermsOfTradeChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 'default',
    qoq: 'default',
    yoy: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value ?? 0,
      qoq: item.qoq ?? 0,
      yoy: item.yoy ?? 0,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    return [...rawChartData].sort((a, b) => a.date.localeCompare(b.date))
  }, [rawChartData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2000,
  })

  // テーブル用データ
  const qoqExtractor = useCallback((item: ChartDataPoint) => item.qoq as number | null, [])
  const qoqTableData = useQuarterlyTableData(chartData, qoqExtractor, 10)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 現在表示中の値と表示ラベル
  const { currentValue, currentLabel, currentFormat } = useMemo(() => {
    if (!latest) return { currentValue: null, currentLabel: '', currentFormat: 'number' as const }

    switch (dataKind) {
      case 'value':
        return {
          currentValue: latest.value,
          currentLabel: '交易条件（指数）',
          currentFormat: 'number' as const,
        }
      case 'qoq':
        return {
          currentValue: latest.qoq,
          currentLabel: '交易条件（前期比）',
          currentFormat: 'percent' as const,
        }
      case 'yoy':
        return {
          currentValue: latest.yoy,
          currentLabel: '交易条件（前年比）',
          currentFormat: 'percent' as const,
        }
      default:
        return { currentValue: null, currentLabel: '', currentFormat: 'number' as const }
    }
  }, [latest, dataKind])

  if (data === null) {
    return <LoadingChart title="交易条件（オーストラリア）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="交易条件（オーストラリア）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // データ比較用のoverlayConfig ID
  const getCompareId = () => {
    switch (dataKind) {
      case 'value': return 'au_terms_of_trade'
      case 'qoq': return 'au_terms_of_trade_qoq'
      case 'yoy': return 'au_terms_of_trade_yoy'
      default: return 'au_terms_of_trade'
    }
  }

  return (
    <div id="au-terms-of-trade-chart">
      <ChartContainer
        title="交易条件"
        showPeriodSelector={false}
        dataSource="ABS"
        sourceUrl="https://www.abs.gov.au/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product/latest-release"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={currentLabel}
          value={currentValue}
          date={latest?.date}
          format={currentFormat}
          decimals={currentFormat === 'number' ? 1 : 2}
          valueColor={COLORS.tot}
          nextRelease={data.next_release}
          dateFormatter={formatQuarterLabel}
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
                  {/* 上段: データ種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      currentMode={dataKind}
                      onChange={setDataKind}
                      options={DATA_KIND_OPTIONS}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${getCompareId()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（qoqのときのみ） */}
                  {dataKind === 'qoq' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクター（ヒートマップ以外で表示） */}
                  {!(dataKind === 'qoq' && displayMode === 'heatmap') && (
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  )}

                  {/* === 指数チャート === */}
                  {dataKind === 'value' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'value', color: COLORS.tot, name: '交易条件（指数）' },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => v.toFixed(1)}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {/* === 前期比チャート === */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'qoq', color: COLORS.tot, name: '交易条件（前期比%）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {/* === 前期比ヒートマップ === */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTable
                      data={qoqTableData}
                      decimals={2}
                      helperText="※ 直近10年間の前期比データ（単位: %）"
                    />
                  )}

                  {/* === 前年比チャート === */}
                  {dataKind === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.tot, name: '交易条件（前年比%）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={true}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_gdp" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
