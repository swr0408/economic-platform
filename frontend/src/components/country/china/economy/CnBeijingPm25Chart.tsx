/**
 * 北京PM2.5濃度チャートコンポーネント
 *
 * 日次データを薄い背景バーで表示し、その上に線を重ねる:
 * - 月平均モード: 日次bar + 月平均line（赤）
 * - 30日移動平均モード: 日次bar + 30MA line（赤）
 *
 * データソース: 手動更新CSV (beijing-air-quality.csv)
 *
 * FMPマッピング: なし
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  StandardBarChart,
} from '../../usa/common/ChartComponents'

import type { CnBeijingPm25Data } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnBeijingPm25Data | null
}

type ViewMode = 'monthly' | 'ma30'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'ma30', label: '30日移動平均' },
  { mode: 'monthly', label: '月平均' },
]

const COLOR_DAILY = 'rgba(135, 206, 235, 0.4)' // skyblue 薄め（背景バー）
const COLOR_LINE = '#DC143C' // 赤（月平均・30MA線）

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

const formatDateDaily = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month, day] = dateStr.split('-')
  return `${year}年${parseInt(month)}月${parseInt(day)}日`
}

// =============================================================================
// データマージ用ヘルパー
// =============================================================================

interface MergedMonthlyPoint {
  date: string
  pm25: number | null
  pm25_avg: number | null
}

interface MergedMa30Point {
  date: string
  pm25: number | null
  pm25_ma30: number | null
}

/** 日次データに月平均をマージ（同月のレコードに月平均値を付与） */
function mergeMonthlyIntoDaily(
  daily: { date: string; pm25: number }[],
  monthly: { date: string; pm25_avg: number }[],
): MergedMonthlyPoint[] {
  // 月平均を YYYY-MM でindex化
  const monthlyMap = new Map<string, number>()
  for (const m of monthly) {
    const ym = m.date.slice(0, 7) // "YYYY-MM"
    monthlyMap.set(ym, m.pm25_avg)
  }

  return daily.map(d => {
    const ym = d.date.slice(0, 7)
    return {
      date: d.date,
      pm25: d.pm25,
      pm25_avg: monthlyMap.get(ym) ?? null,
    }
  })
}

/** 日次データに30MA をマージ（同日のレコードに30MA値を付与） */
function mergeMa30IntoDaily(
  daily: { date: string; pm25: number }[],
  ma30: { date: string; pm25_ma30: number }[],
): MergedMa30Point[] {
  const ma30Map = new Map<string, number>()
  for (const m of ma30) {
    ma30Map.set(m.date, m.pm25_ma30)
  }

  return daily.map(d => ({
    date: d.date,
    pm25: d.pm25,
    pm25_ma30: ma30Map.get(d.date) ?? null,
  }))
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnBeijingPm25Chart({ data }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('ma30')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    monthly: 'default',
    ma30: 5,
  })

  // 月平均モード: 日次 + 月平均マージ
  const mergedMonthly = useMemo(() => {
    if (!data?.daily || !data?.monthly) return []
    return mergeMonthlyIntoDaily(data.daily, data.monthly)
  }, [data])

  // 30MAモード: 日次 + 30MAマージ
  const mergedMa30 = useMemo(() => {
    if (!data?.daily || !data?.ma30) return []
    return mergeMa30IntoDaily(data.daily, data.ma30)
  }, [data])

  const sortedMonthly = useSortedData(mergedMonthly)
  const sortedMa30 = useSortedData(mergedMa30)

  const filteredMonthly = usePeriodFiltering(sortedMonthly, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const filteredMa30 = usePeriodFiltering(sortedMa30, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = sortedMonthly.length > 0 || sortedMa30.length > 0

  if (data === null) {
    return <LoadingChart title="北京PM2.5濃度" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="北京PM2.5濃度" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latestMonthly = data.latest_monthly
  const latestDaily = data.latest

  return (
    <div id="beijing-pm25">
      <ChartContainer
        title="北京PM2.5濃度"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Beijing Air Quality"
        sourceUrl="https://aqicn.org/city/beijing/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={viewMode === 'monthly' ? '月平均PM2.5' : '最新日次PM2.5'}
          value={viewMode === 'monthly' ? (latestMonthly?.pm25_avg ?? null) : (latestDaily?.pm25 ?? null)}
          date={viewMode === 'monthly' ? latestMonthly?.date : latestDaily?.date}
          unit="µg/m³"
          decimals={1}
          valueColor={COLOR_LINE}
          dateFormatter={viewMode === 'monthly' ? formatDateFull : undefined}
        />

        {/* ViewMode + 比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=cn_beijing_pm25', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* PeriodSelector */}
        <PeriodSelector
          onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
          selectedPeriod={currentPeriod}
        />

        {/* 月平均モード: 日次bar（薄い背景）+ 月平均line（赤） */}
        {viewMode === 'monthly' && (
          <StandardBarChart
            data={filteredMonthly}
            bars={[
              { dataKey: 'pm25', color: COLOR_DAILY, name: '日次PM2.5' },
            ]}
            lines={[
              { dataKey: 'pm25_avg', color: COLOR_LINE, name: '月平均', strokeWidth: 2 },
            ]}
            yAxisFormatter={(v) => `${v.toFixed(0)}`}
            yDomain={[0, 'dataMax + 20']}
            xAxisFormatter={formatDateLabel}
            tooltipLabelFormatter={formatDateDaily}
            tooltipValueFormatter={(v) => `${v.toFixed(1)} µg/m³`}
            showZeroLine={false}
          />
        )}

        {/* 30MAモード: 日次bar（薄い背景）+ 30MA line（赤） */}
        {viewMode === 'ma30' && (
          <StandardBarChart
            data={filteredMa30}
            bars={[
              { dataKey: 'pm25', color: COLOR_DAILY, name: '日次PM2.5' },
            ]}
            lines={[
              { dataKey: 'pm25_ma30', color: COLOR_LINE, name: '30日移動平均', strokeWidth: 2 },
            ]}
            yAxisFormatter={(v) => `${v.toFixed(0)}`}
            yDomain={[0, 'dataMax + 20']}
            xAxisFormatter={formatDateLabel}
            tooltipLabelFormatter={formatDateDaily}
            tooltipValueFormatter={(v) => `${v.toFixed(1)} µg/m³`}
            showZeroLine={false}
          />
        )}
      </ChartContainer>
    </div>
  )
}
