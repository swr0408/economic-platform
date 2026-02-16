/**
 * カナダ家計債務返済比率（DSR）チャートコンポーネント
 *
 * 家計債務返済比率（Total / Mortgage / Non-mortgage）の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 11-10-0065-01
 * - Debt service indicators of households, national balance sheet accounts
 *
 * 発表スケジュール:
 * - 四半期
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { CaDebtServiceRatioData } from '../../../../hooks/useDashboardData'

interface CanadaDebtServiceRatioChartProps {
  data: CaDebtServiceRatioData | null
}

type ViewMode = 'total' | 'breakdown'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'total', label: '総合' },
  { mode: 'breakdown', label: '内訳' },
]

// カラー設定
const COLORS = {
  total: CHART_COLORS.primary,
  mortgage: '#e6550d',
  non_mortgage: '#756bb1',
}

export default function CanadaDebtServiceRatioChart({ data }: CanadaDebtServiceRatioChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('total')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    total: 'default' as PeriodType,
    breakdown: 'default' as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        value: item.value,
        mortgage: item.mortgage,
        non_mortgage: item.non_mortgage,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2000,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="家計債務返済比率（DSR）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="家計債務返済比率（DSR）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示内容
  const getLatestItems = () => {
    if (viewMode === 'total') {
      return [
        {
          label: '総合DSR',
          value: latestValue?.value,
          color: COLORS.total,
          format: 'percent' as const,
        },
      ]
    } else {
      return [
        {
          label: '住宅ローン',
          value: latestValue?.mortgage,
          color: COLORS.mortgage,
          format: 'percent' as const,
        },
        {
          label: '非住宅ローン',
          value: latestValue?.non_mortgage,
          color: COLORS.non_mortgage,
          format: 'percent' as const,
        },
      ]
    }
  }

  return (
    <div id="ca-debt-service-ratio-chart">
      <ChartContainer
        title="家計債務返済比率（DSR）"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110006501"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latestValue?.date}
          nextRelease={data.next_release ?? null}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=canada_debt_service_ratio', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* 総合DSR（線グラフ） */}
        {viewMode === 'total' && (
          <StandardLineChart
            data={filteredData}
            lines={[
              { dataKey: 'value', color: COLORS.total, name: '家計DSR（総合）' },
            ]}
            yAxisFormatter={(v) => `${v}%`}
            yDomain={['dataMin - 1', 'dataMax + 1']}
          />
        )}

        {/* 内訳（住宅ローン + 非住宅ローン） */}
        {viewMode === 'breakdown' && (
          <StandardLineChart
            data={filteredData}
            lines={[
              { dataKey: 'mortgage', color: COLORS.mortgage, name: '住宅ローンDSR' },
              { dataKey: 'non_mortgage', color: COLORS.non_mortgage, name: '非住宅ローンDSR' },
            ]}
            yAxisFormatter={(v) => `${v}%`}
            yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          />
        )}
      </ChartContainer>
    </div>
  )
}
