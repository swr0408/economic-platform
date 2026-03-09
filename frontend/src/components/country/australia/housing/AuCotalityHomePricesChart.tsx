/**
 * オーストラリア Cotality住宅価格指数チャートコンポーネント
 *
 * Cotality (旧 CoreLogic) Daily Home Value Index
 * 5 Capital City Aggregate のみ表示
 *
 * ビューモード:
 * - index: 日次インデックス値（線グラフ）
 * - mom: 月次前月比%（棒グラフ）
 *
 * データソース:
 * - Cotality: https://www.cotality.com/au/our-data/indices
 *
 * 発表スケジュール: 日次（Excelファイル手動更新）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
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

import type { AuCotalityHomePricesData } from '../../../../hooks/useDashboardData'

interface AuCotalityHomePricesChartProps {
  data: AuCotalityHomePricesData | null
}

interface DailyChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

interface MonthlyChartDataPoint {
  date: string
  value: number
  mom: number
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  index: '#1E88E5',   // 青
  mom: '#43A047',     // 緑
}

type ViewMode = 'index' | 'mom'

export default function AuCotalityHomePricesChart({ data }: AuCotalityHomePricesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('index')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    index: 10,
    mom: 10,
  })

  // 日次データ
  const dailyChartData = useMemo<DailyChartDataPoint[]>(() => {
    if (!data?.data) return []
    return data.data
      .filter((item) => item.value !== null)
      .map((item) => ({
        date: item.date,
        value: item.value ?? 0,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 月次データ
  const monthlyChartData = useMemo<MonthlyChartDataPoint[]>(() => {
    if (!data?.monthly_data) return []
    return data.monthly_data
      .map((item) => ({
        date: item.date,
        value: item.value ?? 0,
        mom: item.mom ?? 0,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredDailyData = usePeriodFiltering(dailyChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2025,
  })

  const filteredMonthlyData = usePeriodFiltering(monthlyChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2025,
  })

  const hasData = dailyChartData.length > 0

  // 最新値を取得
  const { currentValue, currentLabel, currentColor, currentFormat, currentDecimals } = useMemo(() => {
    if (viewMode === 'index') {
      const latest = dailyChartData.length > 0 ? dailyChartData[dailyChartData.length - 1] : null
      return {
        currentValue: latest?.value ?? null,
        currentLabel: '住宅価格指数（5都市合成）',
        currentColor: COLORS.index,
        currentFormat: 'number' as const,
        currentDecimals: 2,
      }
    }
    // mom
    const latest = monthlyChartData.length > 0 ? monthlyChartData[monthlyChartData.length - 1] : null
    return {
      currentValue: latest?.mom ?? null,
      currentLabel: '住宅価格指数（前月比）',
      currentColor: COLORS.mom,
      currentFormat: 'percent' as const,
      currentDecimals: 2,
    }
  }, [viewMode, dailyChartData, monthlyChartData])

  // 最新日付
  const latestDate = useMemo(() => {
    if (viewMode === 'index') {
      return dailyChartData.length > 0 ? dailyChartData[dailyChartData.length - 1].date : undefined
    }
    return monthlyChartData.length > 0 ? monthlyChartData[monthlyChartData.length - 1].date : undefined
  }, [viewMode, dailyChartData, monthlyChartData])

  // データ比較用のoverlayConfig ID
  const getCompareId = () => {
    switch (viewMode) {
      case 'index': return 'au_cotality_home_prices_index'
      case 'mom': return 'au_cotality_home_prices_mom'
      default: return 'au_cotality_home_prices_index'
    }
  }

  if (data === null) {
    return <LoadingChart title="Cotality住宅価格指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="Cotality住宅価格指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="au-cotality-home-prices-chart">
      <ChartContainer
        title="Cotality住宅価格指数"
        showPeriodSelector={false}
        dataSource="Cotality (formerly CoreLogic)"
        sourceUrl="https://www.cotality.com/au/our-data/indices"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={currentLabel}
          value={currentValue}
          date={latestDate}
          format={currentFormat}
          decimals={currentDecimals}
          valueColor={currentColor}
        />

        {/* ビューモード切替 */}
        <ViewModeButtonGroup
          currentMode={viewMode}
          onChange={(mode) => setViewMode(mode as ViewMode)}
          options={[
            { mode: 'index', label: 'インデックス' },
            { mode: 'mom', label: '前月比' },
          ]}
        />

        {/* 期間セレクター + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open(`/compare?s=${getCompareId()}`, '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* === インデックス値チャート（日次） === */}
        {viewMode === 'index' && (
          <StandardLineChart
            data={filteredDailyData}
            lines={[
              { dataKey: 'value', color: COLORS.index, name: 'HVI (5 Capital City)' },
            ]}
            yAxisFormatter={(v) => `${v.toFixed(0)}`}
            tooltipValueFormatter={(v) => `${v.toFixed(2)}`}
            yDomain={['dataMin - 2', 'dataMax + 2']}
          />
        )}

        {/* === 前月比チャート（月次） === */}
        {viewMode === 'mom' && (
          <StandardBarChart
            data={filteredMonthlyData}
            bars={[
              { dataKey: 'mom', color: COLORS.mom, name: '前月比 (%)' },
            ]}
            yAxisFormatter={(v) => `${v}%`}
          />
        )}
      </ChartContainer>
    </div>
  )
}
