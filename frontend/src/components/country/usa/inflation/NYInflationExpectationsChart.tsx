/**
 * NY連銀インフレ期待チャートコンポーネント
 *
 * NY Fed SCE (Survey of Consumer Expectations) から取得した
 * 1年先・3年先・5年先インフレ期待の中央値を表示
 * データソース: NY Fed
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NYInflationExpectationsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  formatDateLabel,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  type TooltipPayloadItem,
} from '../common/ChartComponents'
import {
  TOOLTIP_STYLE,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  DARK_THEME,
} from '../common/chartConstants'

// =============================================================================
// 型定義
// =============================================================================

interface NYInflationExpectationsChartProps {
  nyInflationExpectationsData: NYInflationExpectationsData | null
}

interface MergedDataPoint {
  date: string
  one_year: number | null
  three_year: number | null
  five_year: number | null
}

// カラー設定
const COLORS = {
  one_year: '#3b82f6',    // 1年先（青）
  three_year: '#22c55e',  // 3年先（緑）
  five_year: '#ef4444',   // 5年先（赤）
}

// 項目の日本語名
const LABELS: Record<string, string> = {
  one_year: '1年先インフレ期待',
  three_year: '3年先インフレ期待',
  five_year: '5年先インフレ期待',
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

function NYInflationExpectationsTooltip({ active, payload, label }: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {formatDateLabel(label || '')}
      </div>
      {payload.map((item, index) => {
        const displayName = LABELS[item.dataKey] || item.name

        return (
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
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {displayName}
            </span>
            <span style={{ fontWeight: 500, color: item.color }}>
              {item.value != null ? `${item.value.toFixed(2)}%` : '-'}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NYInflationExpectationsChart({ nyInflationExpectationsData }: NYInflationExpectationsChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  // データをマージ（3つの系列を1つの配列に結合）
  const mergedData = useMemo((): MergedDataPoint[] => {
    if (!nyInflationExpectationsData?.data) return []

    const { one_year, three_year, five_year } = nyInflationExpectationsData.data

    // 全日付を収集
    const dateSet = new Set<string>()
    one_year?.forEach(d => dateSet.add(d.date))
    three_year?.forEach(d => dateSet.add(d.date))
    five_year?.forEach(d => dateSet.add(d.date))

    // 日付ごとにデータをマージ
    const oneYearMap = new Map(one_year?.map(d => [d.date, d.value]) ?? [])
    const threeYearMap = new Map(three_year?.map(d => [d.date, d.value]) ?? [])
    const fiveYearMap = new Map(five_year?.map(d => [d.date, d.value]) ?? [])

    const result: MergedDataPoint[] = []
    dateSet.forEach(date => {
      result.push({
        date,
        one_year: oneYearMap.get(date) ?? null,
        three_year: threeYearMap.get(date) ?? null,
        five_year: fiveYearMap.get(date) ?? null,
      })
    })

    // 日付昇順でソート
    return result.sort((a, b) => a.date.localeCompare(b.date))
  }, [nyInflationExpectationsData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2021,  // NY Fed SCEは2013年から開始
  })

  // 最新値
  const latestOneYear = useMemo(() => {
    return nyInflationExpectationsData?.latest?.one_year ?? null
  }, [nyInflationExpectationsData])

  const latestThreeYear = useMemo(() => {
    return nyInflationExpectationsData?.latest?.three_year ?? null
  }, [nyInflationExpectationsData])

  const latestFiveYear = useMemo(() => {
    return nyInflationExpectationsData?.latest?.five_year ?? null
  }, [nyInflationExpectationsData])

  const latestDate = useMemo(() => {
    return nyInflationExpectationsData?.latest?.date
  }, [nyInflationExpectationsData])

  const hasData = mergedData.length > 0

  // ローディング状態
  if (nyInflationExpectationsData === null) {
    return <LoadingChart title="NY連銀インフレ期待" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="NY連銀インフレ期待" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ny-inflation-expectations">
      <ChartContainer
        title="NY連銀インフレ期待（中央値）"
        showPeriodSelector={false}
        dataSource="NY Fed SCE"
        sourceUrl="https://www.newyorkfed.org/microeconomics/sce#/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: LABELS.one_year,
              value: latestOneYear,
              color: COLORS.one_year,
              format: 'percent',
            },
            {
              label: LABELS.three_year,
              value: latestThreeYear,
              color: COLORS.three_year,
              format: 'percent',
            },
            {
              label: LABELS.five_year,
              value: latestFiveYear,
              color: COLORS.five_year,
              format: 'percent',
            },
          ]}
          date={latestDate}
          nextRelease={nyInflationExpectationsData?.next_release}
        />

        {/* 期間セレクタ + 比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（NY連銀インフレ期待）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=us_ny_fed_inflation_exp_1y&s=us_ny_fed_inflation_exp_3y&s=us_ny_fed_inflation_exp_5y', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 折れ線グラフ */}
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={AXIS_STYLE.tick}
              interval={AXIS_STYLE.interval}
            />
            <YAxis
              domain={['dataMin - 0.5', 'dataMax + 0.5']}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v}%`}
            />
            <RechartsTooltip content={<NYInflationExpectationsTooltip />} />
            <Legend />
            {/* FRBの2%インフレ目標ライン */}
            <ReferenceLine
              y={2}
              stroke="#fbbf24"
              strokeDasharray="5 5"
              label={{ value: 'FRB目標2%', position: 'insideTopRight', fill: '#fbbf24', fontSize: 12 }}
            />
            <Line
              type="monotone"
              dataKey="one_year"
              stroke={COLORS.one_year}
              strokeWidth={2}
              dot={false}
              name={LABELS.one_year}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              type="monotone"
              dataKey="three_year"
              stroke={COLORS.three_year}
              strokeWidth={2}
              dot={false}
              name={LABELS.three_year}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              type="monotone"
              dataKey="five_year"
              stroke={COLORS.five_year}
              strokeWidth={2}
              dot={false}
              name={LABELS.five_year}
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
