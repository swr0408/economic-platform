/**
 * 家計予想物価上昇率チャート（日銀「生活意識に関するアンケート調査」）
 *
 * データ項目（6系列, %）:
 * - exp1y_median / exp1y_mean   : 1年後の物価予想（中央値 / 平均値）
 * - exp5y_median / exp5y_mean   : 5年後の物価予想（中央値 / 平均値）
 * - current_median / current_mean: 現在の物価実感（前年比）（中央値 / 平均値）
 */

import { useEffect, useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { useHiddenSeries } from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
  DataTypeButtonGroup,
} from '../../usa/common/ChartComponents'

import {
  fetchHouseholdExpectedInflationData,
  formatSurveyMonth,
  formatSurveyMonthShort,
  parseSurveyMonth,
  type HouseholdExpectedInflationResponse,
  type HouseholdExpectedInflationDataPoint,
} from '../../../../utils/japan/householdExpectedInflationApi'

// =============================================================================
// 定数
// =============================================================================

const COLORS = {
  exp1y_median: '#1677ff',   // 1年後 中央値（ヘッドライン）
  exp1y_mean: '#69b1ff',     // 1年後 平均値
  exp5y_median: '#cf1322',   // 5年後 中央値
  exp5y_mean: '#ff9c9c',     // 5年後 平均値
  current_median: '#389e0d', // 現在実感 中央値
  current_mean: '#95de64',   // 現在実感 平均値
}

// 表示する予想ホライズン（ボタンで切替、各2系列＝中央値・平均値）
type Horizon = '1y' | '5y' | 'current'

const HORIZON_OPTIONS: { type: Horizon; label: string }[] = [
  { type: '1y', label: '1年後予想' },
  { type: '5y', label: '5年後予想' },
  { type: 'current', label: '現在の実感' },
]

const HORIZON_CONFIG: Record<
  Horizon,
  {
    label: string
    medianKey: keyof HouseholdExpectedInflationDataPoint
    meanKey: keyof HouseholdExpectedInflationDataPoint
    medianColor: string
    meanColor: string
  }
> = {
  '1y': { label: '1年後予想', medianKey: 'exp1y_median', meanKey: 'exp1y_mean', medianColor: COLORS.exp1y_median, meanColor: COLORS.exp1y_mean },
  '5y': { label: '5年後予想', medianKey: 'exp5y_median', meanKey: 'exp5y_mean', medianColor: COLORS.exp5y_median, meanColor: COLORS.exp5y_mean },
  'current': { label: '現在の実感', medianKey: 'current_median', meanKey: 'current_mean', medianColor: COLORS.current_median, meanColor: COLORS.current_mean },
}

// =============================================================================
// 期間フィルタリング（四半期データ用）
// =============================================================================

const filterByPeriod = (
  data: HouseholdExpectedInflationDataPoint[],
  period: number | 'default' | 'all'
): HouseholdExpectedInflationDataPoint[] => {
  const sorted = [...data].sort((a, b) => {
    const da = parseSurveyMonth(a.date)
    const db = parseSurveyMonth(b.date)
    if (!da || !db) return 0
    return da.getTime() - db.getTime()
  })

  if (period === 'all') return sorted

  const now = new Date()
  let startDate: Date
  if (period === 'default') {
    startDate = new Date(2010, 0, 1)
  } else if (typeof period === 'number') {
    startDate = new Date(now.getFullYear() - period, now.getMonth(), now.getDate())
  } else {
    return sorted
  }

  return sorted.filter((point) => {
    const d = parseSurveyMonth(point.date)
    return d && d >= startDate
  })
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function HouseholdExpectedInflationChart() {
  const [data, setData] = useState<HouseholdExpectedInflationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<number | 'default' | 'all'>('all')
  const [horizon, setHorizon] = useState<Horizon>('1y')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchHouseholdExpectedInflationData()
        if (res.error) {
          setError(res.error)
        } else {
          setData(res)
        }
      } catch (err) {
        console.error('Error loading Household Expected Inflation data:', err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  const filteredData = useMemo(() => {
    if (!data?.data) return []
    return filterByPeriod(data.data, currentPeriod)
  }, [data, currentPeriod])

  const hasData = (data?.data?.length ?? 0) > 0

  if (loading) {
    return <LoadingChart title="家計予想物価上昇率（生活意識アンケート）" />
  }

  if (error) {
    return (
      <ChartContainer title="家計予想物価上昇率（生活意識アンケート）" showPeriodSelector={false} showDataSource={false} handbookId="household-expected-inflation">
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="家計予想物価上昇率（生活意識アンケート）" showPeriodSelector={false} showDataSource={false} handbookId="household-expected-inflation">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest
  const cfg = HORIZON_CONFIG[horizon]

  // 次回発表日のフォーマット
  const formatNextRelease = (): string | null => {
    if (!data?.next_release) return null
    const nr = data.next_release
    if (nr.datetime_jst) {
      const dt = new Date(nr.datetime_jst)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    }
    if (nr.date) {
      const dt = new Date(nr.date)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    }
    return null
  }

  return (
    <div id="household-expected-inflation-chart">
      <ChartContainer
        title="家計予想物価上昇率（生活意識アンケート）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="日本銀行「生活意識に関するアンケート調査」"
        sourceUrl="https://www.boj.or.jp/research/o_survey/index.htm"
        handbookId="household-expected-inflation"
      >
        {/* 最新値表示（選択中ホライズンの中央値・平均値） */}
        <LatestValueBox
          items={[
            { label: `${cfg.label}（中央値）`, value: (latest?.[cfg.medianKey] as number | null) ?? undefined, color: cfg.medianColor, format: 'percent', decimals: 1 },
            { label: `${cfg.label}（平均値）`, value: (latest?.[cfg.meanKey] as number | null) ?? undefined, color: cfg.meanColor, format: 'percent', decimals: 1 },
          ]}
          date={latest?.date}
          dateFormatter={formatSurveyMonth}
          nextRelease={data?.next_release ? { date: formatNextRelease() || '' } : undefined}
        />

        {/* ホライズン切替ボタン + データ比較ボタン（同一行） */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <DataTypeButtonGroup options={HORIZON_OPTIONS} currentType={horizon} onChange={setHorizon} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=household_level_expected_inflation_rate', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間セレクター（単独行） */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* チャート（選択中ホライズンの中央値・平均値の2系列） */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: cfg.medianKey, color: cfg.medianColor, name: `${cfg.label}（中央値）`, hide: hiddenSeries.has(cfg.medianKey) },
            { dataKey: cfg.meanKey, color: cfg.meanColor, name: `${cfg.label}（平均値）`, hide: hiddenSeries.has(cfg.meanKey) },
          ]}
          yAxisFormatter={(v: number) => `${v.toFixed(0)}%`}
          yDomain={['dataMin - 1', 'dataMax + 1']}
          xAxisFormatter={formatSurveyMonthShort}
          tooltipLabelFormatter={formatSurveyMonth}
          tooltipValueFormatter={(v: number) => `${v.toFixed(1)}%`}
          onLegendClick={handleLegendClick}
          showZeroLine={true}
        />
      </ChartContainer>
    </div>
  )
}
