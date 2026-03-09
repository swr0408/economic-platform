/**
 * スイス家計消費（Households and NPISH）チャートコンポーネント
 *
 * SECOから四半期データを取得し、前期比・前年比を表示
 *
 * データ:
 * - QoQ（前期比）- 季節調整済み
 * - YoY（前年比）- 調整前
 *
 * データソース:
 * - SECO (State Secretariat for Economic Affairs)
 *
 * 発表スケジュール:
 * - 四半期ごと（GDPと同時発表、FMPから次回発表日時取得）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { DARK_THEME, TEXT_COLORS, QUARTER_NAMES } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CHHouseholdsAndNpishData } from '../../../../hooks/useDashboardData'

interface CHHouseholdsAndNpishChartProps {
  data: CHHouseholdsAndNpishData | null
}

interface ChartDataPoint {
  date: string
  qoq: number
  yoy: number
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  qoq: '#DC143C', // スイス赤
  yoy: '#1890ff', // 青
}

// 指標種別
type DataKind = 'yoy' | 'qoq'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'qoq', label: '前期比' },
  { mode: 'yoy', label: '前年比' },
]
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// 四半期日付フォーマッター（2025-01-01 → 2025/Q1）
const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}/Q${quarter}`
}

// 日付から年を抽出
const getYearFromDate = (dateStr: string): number => {
  return parseInt(dateStr.split('-')[0], 10)
}

// 日付から四半期を抽出（0-indexed）
const getQuarterFromDate = (dateStr: string): number => {
  const month = parseInt(dateStr.split('-')[1], 10)
  return Math.floor((month - 1) / 3)
}

export default function CHHouseholdsAndNpishChart({ data }: CHHouseholdsAndNpishChartProps) {
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

  // テーブル用データ（年別×四半期のマトリックス）
  const tableData = useMemo(() => {
    if (!chartData.length) return { years: [] as number[], quarterlyData: {} as Record<number, Record<number, number | null>> }

    const years = new Set<number>()
    const quarterlyData: Record<number, Record<number, number | null>> = {}

    chartData.forEach(item => {
      const year = getYearFromDate(item.date)
      const quarter = getQuarterFromDate(item.date)

      if (year > 0) {
        years.add(year)
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = item.qoq
      }
    })

    // 直近10年間のみ
    const sortedYears = Array.from(years).sort((a, b) => b - a).slice(0, 10).reverse()

    return { years: sortedYears, quarterlyData }
  }, [chartData])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 現在表示中の値を取得
  const currentValue = useMemo(() => {
    if (!latest) return null
    if (dataKind === 'yoy') return latest.yoy
    return latest.qoq
  }, [latest, dataKind])

  // 現在の色を取得
  const currentColor = useMemo(() => {
    if (dataKind === 'yoy') return COLORS.yoy
    return COLORS.qoq
  }, [dataKind])

  if (data === null) {
    return <LoadingChart title="家計消費" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="家計消費" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // テーブルセルの背景色を決定
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 0.5) return 'rgba(16, 185, 129, 0.55)'
    if (value > 0.25) return 'rgba(16, 185, 129, 0.35)'
    if (value > 0) return 'rgba(16, 185, 129, 0.15)'
    if (value < -0.5) return 'rgba(239, 68, 68, 0.55)'
    if (value < -0.25) return 'rgba(239, 68, 68, 0.35)'
    if (value < 0) return 'rgba(239, 68, 68, 0.15)'
    return 'transparent'
  }

  // テーブルコンポーネント
  const ConsumptionTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 13,
          textAlign: 'center',
          color: DARK_THEME.textPrimary,
        }}
      >
        <thead>
          <tr style={{ backgroundColor: DARK_THEME.bgTertiary }}>
            <th style={{ padding: '10px 8px', borderBottom: `2px solid ${DARK_THEME.borderLight}`, fontWeight: 'bold' }}>
              年
            </th>
            {QUARTER_NAMES.map((quarter, idx) => (
              <th
                key={idx}
                style={{
                  padding: '10px 8px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 80,
                }}
              >
                {quarter}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tableData.years.map((year: number) => (
            <tr key={year}>
              <td
                style={{
                  padding: '8px',
                  borderBottom: `1px solid ${DARK_THEME.border}`,
                  fontWeight: 'bold',
                  backgroundColor: DARK_THEME.bgTertiary,
                }}
              >
                {year}
              </td>
              {Array.from({ length: 4 }, (_, quarter) => {
                const value = tableData.quarterlyData[year]?.[quarter]
                return (
                  <td
                    key={quarter}
                    style={{
                      padding: '8px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      backgroundColor: getCellColor(value),
                    }}
                  >
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(2)}
                      </span>
                    ) : (
                      <span style={{ color: TEXT_COLORS.quaternary }}>-</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 8, fontSize: 11, color: TEXT_COLORS.tertiary, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(16, 185, 129, 0.55)', marginRight: 4 }} />
          プラス（+0.5%以上）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(16, 185, 129, 0.35)', marginRight: 4 }} />
          プラス（0〜+0.5%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.35)', marginRight: 4 }} />
          マイナス（0〜-0.5%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(239, 68, 68, 0.55)', marginRight: 4 }} />
          マイナス（-0.5%以下）
        </span>
      </div>
    </div>
  )

  // データ比較用のoverlayConfig ID
  const getCompareId = () => {
    if (dataKind === 'yoy') return 'ch_households_and_npish_yoy'
    return 'ch_households_and_npish_qoq'
  }

  const getChartTitle = () => {
    if (dataKind === 'yoy') return '家計消費（前年比）'
    return '家計消費（前期比）'
  }

  return (
    <div id="ch-households-and-npish-chart">
      <ChartContainer
        title="家計消費"
        showPeriodSelector={false}
        dataSource="SECO (State Secretariat for Economic Affairs)"
        sourceUrl="https://www.seco.admin.ch/seco/de/home/wirtschaftslage---wirtschaftspolitik/Wirtschaftslage/bip-quartalsschaetzungen-.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getChartTitle()}
          value={currentValue}
          date={latest?.date}
          format="percent"
          decimals={2}
          valueColor={currentColor}
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${getCompareId()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {dataKind === 'qoq' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクター */}
                  {!(dataKind === 'qoq' && displayMode === 'heatmap') && (
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  )}

                  {/* コンテンツ表示 */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && <ConsumptionTable />}

                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'qoq', color: COLORS.qoq, name: '家計消費（前期比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {dataKind === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '家計消費（前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
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
                <MarketImpactTab indicatorId="ch_households_and_npish" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
