/**
 * スイス住宅ローン金利チャートコンポーネント
 *
 * SNB Data Portalからの住宅ローン金利（新規契約）を表示
 * - 変動金利（50万〜100万CHF, 100万〜500万CHF）
 * - 固定金利（50万〜100万CHF, 100万〜500万CHF）
 *
 * データソース:
 * - SNB Data Portal: https://data.snb.ch/
 *
 * 発表スケジュール:
 * - 月次（Monthly banking statistics）- 20日以降の最初の営業日 09:00（チューリッヒ時間）
 */
import { useMemo, useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'

// 型定義
import type { CHMortgageRatesData } from '../../../../hooks/useDashboardData'

interface CHMortgageRatesChartProps {
  data: CHMortgageRatesData | null
}

interface ChartDataPoint {
  date: string
  variable_500k_1m: number | null
  variable_1m_5m: number | null
  fixed_500k_1m: number | null
  fixed_1m_5m: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  variable_500k_1m: '#FF6B6B', // 赤系（変動金利 小額）
  variable_1m_5m: '#FF8E53',   // オレンジ系（変動金利 大額）
  fixed_500k_1m: '#4169E1',    // 青系（固定金利 小額）
  fixed_1m_5m: '#00CED1',      // シアン系（固定金利 大額）
}

// 表示モード
type ViewMode = 'all' | 'variable' | 'fixed'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'all', label: '全て' },
  { mode: 'variable', label: '変動金利' },
  { mode: 'fixed', label: '固定金利' },
]

export default function CHMortgageRatesChart({ data }: CHMortgageRatesChartProps) {
  // 表示モード（変動金利 / 固定金利 / 全て）
  const [viewMode, setViewMode] = useState<ViewMode>('all')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      variable_500k_1m: item.variable_500k_1m,
      variable_1m_5m: item.variable_1m_5m,
      fixed_500k_1m: item.fixed_500k_1m,
      fixed_1m_5m: item.fixed_1m_5m,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      const item = chartData[i]
      if (
        item.variable_500k_1m !== null ||
        item.variable_1m_5m !== null ||
        item.fixed_500k_1m !== null ||
        item.fixed_1m_5m !== null
      ) {
        return item
      }
    }
    return null
  }, [chartData])

  // 現在のビューモードに応じた最新値を取得
  const currentLatestValue = useMemo(() => {
    if (!latestValue) return null
    if (viewMode === 'variable') return latestValue.variable_500k_1m
    if (viewMode === 'fixed') return latestValue.fixed_500k_1m
    return latestValue.variable_500k_1m // all の場合は変動金利を表示
  }, [latestValue, viewMode])

  // 現在のビューモードに応じた色を取得
  const currentColor = useMemo(() => {
    if (viewMode === 'variable') return COLORS.variable_500k_1m
    if (viewMode === 'fixed') return COLORS.fixed_500k_1m
    return COLORS.variable_500k_1m
  }, [viewMode])

  // 表示する系列を取得
  const getLines = () => {
    if (viewMode === 'variable') {
      return [
        { dataKey: 'variable_500k_1m', color: COLORS.variable_500k_1m, name: '変動（50万〜100万）' },
        { dataKey: 'variable_1m_5m', color: COLORS.variable_1m_5m, name: '変動（100万〜500万）' },
      ]
    } else if (viewMode === 'fixed') {
      return [
        { dataKey: 'fixed_500k_1m', color: COLORS.fixed_500k_1m, name: '固定（50万〜100万）' },
        { dataKey: 'fixed_1m_5m', color: COLORS.fixed_1m_5m, name: '固定（100万〜500万）' },
      ]
    }
    // all
    return [
      { dataKey: 'variable_500k_1m', color: COLORS.variable_500k_1m, name: '変動（50万〜100万）' },
      { dataKey: 'variable_1m_5m', color: COLORS.variable_1m_5m, name: '変動（100万〜500万）' },
      { dataKey: 'fixed_500k_1m', color: COLORS.fixed_500k_1m, name: '固定（50万〜100万）' },
      { dataKey: 'fixed_1m_5m', color: COLORS.fixed_1m_5m, name: '固定（100万〜500万）' },
    ]
  }

  // 最新値ラベルを取得
  const getLatestLabel = () => {
    if (viewMode === 'variable') return '住宅ローン金利（変動）'
    if (viewMode === 'fixed') return '住宅ローン金利（固定）'
    return '住宅ローン金利（変動）'
  }

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="住宅ローン金利" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="住宅ローン金利" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-mortgage-rates-chart">
      <ChartContainer
        title="住宅ローン金利"
        showPeriodSelector={false}
        dataSource="Swiss National Bank"
        sourceUrl="https://data.snb.ch/en/topics/ziredev/cube/zikredvol"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getLatestLabel()}
          value={currentLatestValue}
          date={latestValue?.date}
          format="percent"
          decimals={2}
          valueColor={currentColor}
          nextRelease={data.next_release ? { date: data.next_release } : null}
        />

        {/* ビューモード切替 */}
        <ViewModeButtonGroup
          options={VIEW_MODE_OPTIONS}
          currentMode={viewMode}
          onChange={setViewMode}
        />

        {/* 期間セレクター・データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ch_mortgage_rates_variable&s=ch_mortgage_rates_fixed', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={getLines()}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
          yDomain={['dataMin - 0.2', 'dataMax + 0.2']}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
