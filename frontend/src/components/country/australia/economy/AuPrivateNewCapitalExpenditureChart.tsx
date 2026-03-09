/**
 * オーストラリア民間新規設備投資チャートコンポーネント
 *
 * ABSからPrivate New Capital Expenditureデータを取得し表示
 *
 * データ:
 * - value: レベル値 ($m AUD, Current Prices, SA)
 * - qoq: 前期比 (%)
 * - yoy: 前年比 (%)
 *
 * データソース:
 * - ABS (Australian Bureau of Statistics) 5625.0
 *
 * 発表スケジュール:
 * - 四半期ごと
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

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuPrivateNewCapitalExpenditureData } from '../../../../hooks/useDashboardData'

interface AuPrivateNewCapitalExpenditureChartProps {
  data: AuPrivateNewCapitalExpenditureData | null
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
  capex: '#8E44AD',  // 紫系
}

// データ種別
type DataKind = 'yoy' | 'qoq'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'qoq', label: '前期比' },
  { mode: 'yoy', label: '前年比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// 四半期日付フォーマッター（2025-Q3 → 2025/Q3）
const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  return dateStr.replace('-', '/')
}

export default function AuPrivateNewCapitalExpenditureChart({ data }: AuPrivateNewCapitalExpenditureChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('qoq')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    qoq: 20,
    yoy: 20,
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
    defaultStartYear: 2015,
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
  const { currentValue, currentLabel } = useMemo(() => {
    if (!latest) return { currentValue: null, currentLabel: '' }

    switch (dataKind) {
      case 'qoq':
        return {
          currentValue: latest.qoq,
          currentLabel: '民間設備投資（前期比）',
        }
      case 'yoy':
        return {
          currentValue: latest.yoy,
          currentLabel: '民間設備投資（前年比）',
        }
      default:
        return { currentValue: null, currentLabel: '' }
    }
  }, [latest, dataKind])

  if (data === null) {
    return <LoadingChart title="民間新規設備投資" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="民間新規設備投資" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // データ比較用のoverlayConfig ID
  const getCompareId = () => {
    switch (dataKind) {
      case 'qoq': return 'au_private_capex_qoq'
      case 'yoy': return 'au_private_capex_yoy'
      default: return 'au_private_capex_qoq'
    }
  }

  return (
    <div id="au-private-capex-chart">
      <ChartContainer
        title="民間新規設備投資"
        showPeriodSelector={false}
        dataSource="ABS (Australian Bureau of Statistics)"
        sourceUrl="https://www.abs.gov.au/statistics/economy/business-indicators/private-new-capital-expenditure-and-expected-expenditure-australia"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={currentLabel}
          value={currentValue}
          date={latest?.date}
          format="percent"
          decimals={2}
          valueColor={COLORS.capex}
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

                  {/* === 前期比チャート === */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'qoq', color: COLORS.capex, name: '民間設備投資（前期比%）' },
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
                        { dataKey: 'yoy', color: COLORS.capex, name: '民間設備投資（前年比%）' },
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
                <MarketImpactTab indicatorId="au_private_new_capital_expenditure" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
