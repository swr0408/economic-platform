/**
 * 中国 商業住宅販売（Commercial Residential Sales）チャートコンポーネント
 *
 * 3系列の累積前年比（YoY%）を折れ線グラフで表示:
 * - 新規着工床面積（住宅）累積YoY
 * - 新築商業ビル販売額 累積YoY
 * - 新築商業用ビル売却床面積 累積YoY
 *
 * データソース: 国家統計局（NBS）
 *
 * FMPマッピング: なし（マーケットインパクトタブなし）
 */
import { useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { CnCommercialResidentialSalesData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnCommercialResidentialSalesData | null
}

const COLOR_FLOOR_STARTED = '#ef4444'  // 赤
const COLOR_SALES         = '#3b82f6'  // 青
const COLOR_FLOOR_SOLD    = '#f59e0b'  // オレンジ

const SERIES_CONFIG = [
  { dataKey: 'floor_started_yoy', color: COLOR_FLOOR_STARTED, name: '新規着工床面積（住宅）' },
  { dataKey: 'sales_yoy',         color: COLOR_SALES,         name: '販売額' },
  { dataKey: 'floor_sold_yoy',    color: COLOR_FLOOR_SOLD,    name: '売却床面積' },
]

// =============================================================================
// 日付フォーマット
// =============================================================================

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

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnCommercialResidentialSalesChart({ data }: Props) {
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('raw', { raw: 10 })
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 凡例クリックで hide プロパティを設定（全系列を渡して凡例を維持）
  const linesWithHide = useMemo(
    () => SERIES_CONFIG.map(s => ({ ...s, hide: hiddenSeries.has(s.dataKey) })),
    [hiddenSeries]
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="商業住宅販売" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="商業住宅販売" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="commercial-residential-sales">
      <ChartContainer
        title="商業住宅販売"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="国家統計局（NBS）"
        sourceUrl="https://www.stats.gov.cn/english/PressRelease/index.html"
      >
        {/* 最新値表示（3系列） */}
        <LatestValueBox
          items={[
            { label: '新規着工床面積（住宅）', value: latest?.floor_started_yoy, color: COLOR_FLOOR_STARTED, format: 'percent', decimals: 1 },
            { label: '販売額', value: latest?.sales_yoy, color: COLOR_SALES, format: 'percent', decimals: 1 },
            { label: '売却床面積', value: latest?.floor_sold_yoy, color: COLOR_FLOOR_SOLD, format: 'percent', decimals: 1 },
          ]}
          date={latest?.date}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ?? null}
        />

        {/* データ比較ボタン（右寄せ） */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=cn_commercial_residential_sales', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector
          onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
          selectedPeriod={currentPeriod}
        />

        {/* グラフ（3系列折れ線） */}
        <StandardLineChart
          data={filteredData}
          lines={linesWithHide}
          yAxisFormatter={(v) => `${v.toFixed(0)}%`}
          yDomain={['dataMin - 5', 'dataMax + 5']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
          showZeroLine={true}
          showLegend={true}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
