/**
 * Advance Real Retail and Food Services Sales チャートコンポーネント
 *
 * FRED RRSFS シリーズから取得した実質小売売上高データを表示
 * - 前年比: YoY変化率（%）
 * - 前月比: MoM変化率（%）
 *
 * データソース: FRED
 * https://fred.stlouisfed.org/series/RRSFS
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { AdvanceRealRetailSalesData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  formatDateLabelJP,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  SimpleLatestValueBox,
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTable } from '../common/MonthlyTable'


// =============================================================================
// 型定義
// =============================================================================

interface AdvanceRealRetailSalesChartProps {
  data: AdvanceRealRetailSalesData | null
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'mom_chart', label: '前月比' },
  { mode: 'mom_table', label: '前月比（テーブル）' },
  { mode: 'yoy', label: '前年比' },
]

// カラー設定
const COLORS = {
  yoy: CHART_COLORS.positive,
  mom: CHART_COLORS.orange,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AdvanceRealRetailSalesChart({ data }: AdvanceRealRetailSalesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('mom_chart')

  // ビューモード毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // 月別テーブルデータ
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom, 10)

  const hasData = chartData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="実質小売売上高" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer
        title="実質小売売上高"
        showPeriodSelector={false}
        showDataSource={false}
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  // サブラベル・サブバリューの取得
  const getSubInfo = () => {
    if (viewMode === 'yoy') {
      return { label: '前年比', value: latest?.yoy }
    }
    if (viewMode === 'mom_table' || viewMode === 'mom_chart') {
      return { label: '前月比', value: latest?.mom }
    }
    return { label: undefined, value: undefined }
  }

  const subInfo = getSubInfo()

  return (
    <div id="advance-real-retail-sales">
      <ChartContainer
        title="実質小売売上高"
        showPeriodSelector={false}
        dataSource="Census Bureau"
        sourceUrl="https://www.census.gov/retail/index.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="前年比"
          value={latest?.yoy}
          valueColor={COLORS.yoy}
          subLabel={viewMode !== 'yoy' ? subInfo.label : undefined}
          subValue={viewMode !== 'yoy' ? subInfo.value : undefined}
          subValueColor={COLORS.mom}
          date={latest?.date}
          nextRelease={data.next_release}
          format="percent"
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
              onClick={() => window.open('/compare?s=advance_real_retail_sales_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 前年比グラフ */}
        {viewMode === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'yoy', color: COLORS.yoy, name: '前年比' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 2', 'dataMax + 2']}
              tooltipLabelFormatter={formatDateLabelJP}
              showLegend={false}
            />
          </>
        )}

        {/* 前月比テーブル */}
        {viewMode === 'mom_table' && (
          <MonthlyTable
            data={momTableData}
            thresholdType="default"
            showLegend={true}
          />
        )}

        {/* 前月比グラフ */}
        {viewMode === 'mom_chart' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardBarChart
              data={filteredData}
              bars={[
                { dataKey: 'mom', color: COLORS.mom, name: '前月比' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 1', 'dataMax + 1']}
              tooltipLabelFormatter={formatDateLabelJP}
            />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
