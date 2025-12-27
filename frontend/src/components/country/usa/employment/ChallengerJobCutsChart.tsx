/**
 * Challenger人員削減数チャートコンポーネント
 *
 * Investing.com から取得したデータを使用して表示
 * - Challenger Job Cuts: 人員削減発表数
 *
 * 表示モード:
 * - 現数値（レベル）: 人員削減数を棒グラフで表示
 * - 前年比グラフ: 前年比を棒グラフで表示
 * - 前月比グラフ: 前月比を棒グラフで表示
 * - 前月比テーブル: 月別×年別のマトリックス表示
 *
 * 共通コンポーネントを使用
 */
import { useState, useMemo } from 'react'
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { ChallengerJobCutsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  MONTH_NAMES,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TOOLTIP_STYLE,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  TableLegend,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface ChallengerJobCutsChartProps {
  data: ChallengerJobCutsData | null
}

type ViewMode = 'value' | 'yoy_chart' | 'mom_chart' | 'mom_table'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'yoy_chart', label: '前年比グラフ' },
  { mode: 'mom_chart', label: '前月比グラフ' },
  { mode: 'mom_table', label: '前月比テーブル' },
]

// カラー設定
const CHALLENGER_COLOR = '#fa541c'  // オレンジ

// 前月比テーブルの凡例
const MOM_LEGEND = [
  { color: 'rgba(255, 77, 79, 0.3)', label: '+100%以上' },
  { color: 'rgba(255, 77, 79, 0.15)', label: '0〜+100%' },
  { color: 'rgba(82, 196, 26, 0.15)', label: '0〜-50%' },
  { color: 'rgba(82, 196, 26, 0.3)', label: '-50%以下' },
]

// =============================================================================
// ヘルパー関数
// =============================================================================

/** 前月比用のセル背景色を取得 */
function getMomCellColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'transparent'
  // 人員削減数は増加がネガティブ、減少がポジティブ
  if (value > 100) return 'rgba(255, 77, 79, 0.3)'
  if (value > 0) return 'rgba(255, 77, 79, 0.15)'
  if (value < -50) return 'rgba(82, 196, 26, 0.3)'
  if (value < 0) return 'rgba(82, 196, 26, 0.15)'
  return 'transparent'
}

/** 数値をk形式でフォーマット（小数点第3位まで）
 * 値は既にk単位（千人）で取得されるためそのまま表示
 */
function formatNumber(value: number | null): string {
  if (value === null) return 'N/A'
  return `${value.toFixed(3)}k`
}

/**
 * 発表日から対象月を計算
 * - 月初旬（1-15日）に発表 → 前月分のデータ
 * - 月後半（16-31日）に発表 → 当月分のデータ
 */
function getTargetMonth(date: Date): Date {
  if (date.getDate() <= 15) {
    // 月初旬の発表 → 前月分
    return new Date(date.getFullYear(), date.getMonth() - 1, 1)
  } else {
    // 月後半の発表 → 当月分
    return new Date(date.getFullYear(), date.getMonth(), 1)
  }
}

/** 日付を対象月形式でフォーマット（YYYY年M月分）
 * 発表日から対象月を計算して表示
 * 例: 2025-02-06 → 2025年1月分（1月分のデータが2月6日に発表）
 * 例: 2024-10-31 → 2024年10月分（月末発表の場合は当月分）
 */
function formatTargetMonth(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr

  const targetDate = getTargetMonth(date)
  return `${targetDate.getFullYear()}年${targetDate.getMonth() + 1}月`
}

/** X軸用の日付フォーマット（YY/MM形式で対象月を表示） */
function formatDateLabelTarget(dateStr: string): string {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr

  const targetDate = getTargetMonth(date)
  const year = targetDate.getFullYear().toString().slice(-2)
  const month = (targetDate.getMonth() + 1).toString().padStart(2, '0')
  return `${year}/${month}`
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

interface TooltipPayload {
  name: string
  value: number
  color: string
  dataKey: string
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
}

function ValueTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatTargetMonth(label || '')}
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
            padding: '4px 12px',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16 }}>
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
            {item.name}
          </span>
          <span style={{ fontWeight: 500 }}>
            {item.value.toFixed(3)}k
          </span>
        </div>
      ))}
    </div>
  )
}

function PercentTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatTargetMonth(label || '')}
      </div>
      {payload.map((item, index) => {
        const value = item.value
        const sign = value >= 0 ? '+' : ''
        // 人員削減数は増加がネガティブ（赤）、減少がポジティブ（緑）
        const color = value >= 0 ? '#ff4d4f' : '#52c41a'
        return (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
              padding: '4px 12px',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16 }}>
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
              {item.name}
            </span>
            <span style={{ fontWeight: 500, color }}>
              {sign}{value.toFixed(1)}%
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

export default function ChallengerJobCutsChart({ data }: ChallengerJobCutsChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    yoy_chart: 'default',
    mom_chart: 3,
    mom_table: 'default',
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×月別のマトリックス）
  // 対象月ベースで整理（発表日から対象月を計算）
  // 同じ対象月に複数データがある場合は最新の発表日のデータを使用
  const momTableData = useMemo(() => {
    if (sortedData.length === 0) return { years: [] as number[], monthlyData: {} as Record<number, Record<number, number | null>> }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    // 発表日も含めて管理（同一対象月で複数データがある場合の対応）
    const monthlyData: Record<number, Record<number, number | null>> = {}
    const announceDateMap: Record<string, string> = {} // key: "year-month", value: announce date

    sortedData.forEach((item) => {
      const date = new Date(item.date)
      // 対象月を計算（発表日から）
      const targetDate = getTargetMonth(date)
      const year = targetDate.getFullYear()
      const month = targetDate.getMonth()
      const key = `${year}-${month}`

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        // 既存データより新しい発表日の場合のみ更新
        if (!announceDateMap[key] || item.date > announceDateMap[key]) {
          monthlyData[year][month] = item.mom
          announceDateMap[key] = item.date
        }
      }
    })

    return { years, monthlyData }
  }, [sortedData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="Challenger人員削減数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="Challenger人員削減数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    if (viewMode === 'value') {
      return [
        { label: '人員削減数', value: formatNumber(latest.value), color: CHALLENGER_COLOR },
      ]
    } else if (viewMode === 'yoy_chart') {
      const yoy = latest.yoy
      const sign = yoy !== null && yoy >= 0 ? '+' : ''
      // 人員削減数は増加がネガティブ
      const color = yoy !== null && yoy >= 0 ? CHART_COLORS.negative : CHART_COLORS.positive
      return [
        { label: '前年比', value: yoy !== null ? `${sign}${yoy.toFixed(1)}%` : 'N/A', color },
      ]
    } else {
      const mom = latest.mom
      const sign = mom !== null && mom >= 0 ? '+' : ''
      // 人員削減数は増加がネガティブ
      const color = mom !== null && mom >= 0 ? CHART_COLORS.negative : CHART_COLORS.positive
      return [
        { label: '前月比', value: mom !== null ? `${sign}${mom.toFixed(1)}%` : 'N/A', color },
      ]
    }
  }

  // 前月比テーブルコンポーネント
  const MomTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ fontSize: 11, color: '#888', marginBottom: 12 }}>
        ※ 直近10年間の前月比データ（増加はネガティブ・減少はポジティブ）
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'center' }}>
        <thead>
          <tr style={{ backgroundColor: '#fafafa' }}>
            <th style={{ padding: '8px 4px', borderBottom: '2px solid #d9d9d9', fontWeight: 'bold' }}>年</th>
            {MONTH_NAMES.map((month, idx) => (
              <th key={idx} style={{ padding: '8px 4px', borderBottom: '2px solid #d9d9d9', fontWeight: 'bold', minWidth: 55 }}>
                {month}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {momTableData.years.map((year: number) => (
            <tr key={year}>
              <td style={{ padding: '6px 4px', borderBottom: '1px solid #e8e8e8', fontWeight: 'bold', backgroundColor: '#fafafa' }}>
                {year}
              </td>
              {Array.from({ length: 12 }, (_, month) => {
                const value = momTableData.monthlyData[year]?.[month]

                return (
                  <td key={month} style={{ padding: '6px 4px', borderBottom: '1px solid #e8e8e8', backgroundColor: getMomCellColor(value) }}>
                    {value !== null && value !== undefined ? (
                      // 人員削減数は増加がネガティブ（赤）、減少がポジティブ（緑）
                      <span style={{ color: value >= 0 ? '#cf1322' : '#389e0d' }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(1)}%
                      </span>
                    ) : (
                      <span style={{ color: '#bfbfbf' }}>-</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <TableLegend items={MOM_LEGEND} />
    </div>
  )

  return (
    <div id="challenger-job-cuts">
      <ChartContainer
        title="チャレンジャー人員削減数"
        showPeriodSelector={false}
        dataSource="Challenger, Gray & Christmas"
        sourceUrl="https://www.challengergray.com/blog/category/job-cuts-report/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date ? formatTargetMonth(latest.date) : undefined}
          nextRelease={nextRelease}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 現数値グラフ */}
        {viewMode === 'value' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <ResponsiveContainer width="100%" height={450}>
              <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDateLabelTarget}
                  tick={AXIS_STYLE.tick}
                  interval={AXIS_STYLE.interval}
                />
                <YAxis
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v) => `${v.toFixed(0)}k`}
                  domain={['dataMin - 10', 'dataMax + 10']}
                />
                <Tooltip content={<ValueTooltip />} />
                <Legend />
                <Bar
                  dataKey="value"
                  fill={CHALLENGER_COLOR}
                  name="人員削減数"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前年比グラフ */}
        {viewMode === 'yoy_chart' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <ResponsiveContainer width="100%" height={450}>
              <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDateLabelTarget}
                  tick={AXIS_STYLE.tick}
                  interval={AXIS_STYLE.interval}
                />
                <YAxis
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`}
                  domain={['dataMin - 20', 'dataMax + 20']}
                />
                <Tooltip content={<PercentTooltip />} />
                <Legend />
                <ReferenceLine y={0} stroke="#000" strokeWidth={1} />
                <Bar
                  dataKey="yoy"
                  fill={CHALLENGER_COLOR}
                  name="前年比"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前月比グラフ */}
        {viewMode === 'mom_chart' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <ResponsiveContainer width="100%" height={450}>
              <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDateLabelTarget}
                  tick={AXIS_STYLE.tick}
                  interval={AXIS_STYLE.interval}
                />
                <YAxis
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`}
                  domain={['dataMin - 50', 'dataMax + 50']}
                />
                <Tooltip content={<PercentTooltip />} />
                <Legend />
                <ReferenceLine y={0} stroke="#000" strokeWidth={1} />
                <Bar
                  dataKey="mom"
                  fill={CHALLENGER_COLOR}
                  name="前月比"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前月比テーブル */}
        {viewMode === 'mom_table' && <MomTable />}
      </ChartContainer>
    </div>
  )
}
