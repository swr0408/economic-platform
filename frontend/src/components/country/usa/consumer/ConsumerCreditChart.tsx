/**
 * クレジットカードローン残高チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { ConsumerCreditData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatDateLabelJP,
  createPercentFormatter,
  createDollarFormatter,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  SimpleLatestValueBox,
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'


// =============================================================================
// 型定義
// =============================================================================

interface ConsumerCreditChartProps {
  data: ConsumerCreditData | null
}

type ViewMode = 'value' | 'yoy' | 'mom'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'value', label: '原数値' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

// カラー設定
const COLORS = {
  value: CHART_COLORS.magenta,
  yoy: CHART_COLORS.positive,
  mom: CHART_COLORS.primary,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ConsumerCreditChart({ data }: ConsumerCreditChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')

  // ビューモード毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 20,
    yoy: 20,
    mom: 3,
  })

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="クレジットカードローン残高（月平均）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer
        title="クレジットカードローン残高（月平均）"
        showPeriodSelector={false}
        showDataSource={false}
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="consumer-credit">
      <ChartContainer
        title="クレジットカードローン残高"
        showPeriodSelector={false}
        dataSource="Federal Reserve"
        sourceUrl="https://www.federalreserve.gov/releases/h8/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="最新値"
          value={latest?.value}
          valueColor={COLORS.value}
          subLabel={viewMode === 'yoy' ? '前年比' : viewMode === 'mom' ? '前月比' : undefined}
          subValue={viewMode === 'yoy' ? latest?.yoy : viewMode === 'mom' ? latest?.mom : undefined}
          subValueColor={viewMode === 'yoy' ? (latest?.yoy && latest.yoy >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative) : CHART_COLORS.primary}
          date={latest?.date}
          nextRelease={data.next_release}
          format="currency"
          unit="B"
        />

        {/* ビューモード切り替え */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <ViewModeButtonGroup
            options={VIEW_MODE_OPTIONS}
            currentMode={viewMode}
            onChange={setViewMode}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=consumer_credit', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間セレクター */}
        <PeriodSelector
          onPeriodChange={setCurrentPeriod}
          selectedPeriod={currentPeriod}
        />

        {/* 原数値グラフ */}
        {viewMode === 'value' && (
          <StandardLineChart
            data={filteredData}
            lines={[
              { dataKey: 'value', color: COLORS.value, name: 'クレジットカードローン残高' },
            ]}
            yAxisFormatter={(v) => `$${v}B`}
            yDomain={['dataMin - 50', 'dataMax + 50']}
            tooltipLabelFormatter={formatDateLabelJP}
            tooltipFormatter={createDollarFormatter(2, 1)}
            showZeroLine={false}
            showLegend={false}
          />
        )}

        {/* 前年比グラフ */}
        {viewMode === 'yoy' && (
          <StandardLineChart
            data={filteredData}
            lines={[
              { dataKey: 'yoy', color: COLORS.yoy, name: '前年比' },
            ]}
            yAxisFormatter={(v) => `${v}%`}
            yDomain={['dataMin - 3', 'dataMax + 3']}
            tooltipLabelFormatter={formatDateLabelJP}
            tooltipFormatter={createPercentFormatter()}
            showLegend={false}
          />
        )}

        {/* 前月比グラフ */}
        {viewMode === 'mom' && (
          <StandardBarChart
            data={filteredData}
            bars={[
              { dataKey: 'mom', color: COLORS.mom, name: '前月比' },
            ]}
            yAxisFormatter={(v) => `${v}%`}
            yDomain={['dataMin - 1', 'dataMax + 1']}
            tooltipLabelFormatter={formatDateLabelJP}
            tooltipFormatter={createPercentFormatter()}
            showLegend={false}
          />
        )}
      </ChartContainer>
    </div>
  )
}
