/**
 * NAIRU / 失業率 比較チャートコンポーネント
 *
 * FRED NROU（自然失業率 / NAIRU、CBO推計・四半期）と
 * UNRATE（実際の失業率 / U-3、月次）を1つの折れ線グラフで比較表示する。
 * NROUは四半期始月のみ値を持つため、StandardLineChart の connectNulls で連続線として描画される。
 */
import { useMemo, useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { NairuData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
  createPercentFormatter,
  useHiddenSeries,
} from '../common/useChartData'
import {
  SimpleLatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface NairuChartProps {
  data: NairuData | null
}

// カラー設定
const COLORS = {
  unrate: CHART_COLORS.primary, // 実際の失業率
  nairu: '#cf1322',             // NAIRU（自然失業率）
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NairuChart({ data }: NairuChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>(20)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod,
    defaultStartYear: 2000,
  })

  // 最新の実際の失業率（data末尾はNAIRU将来見通し行=unrate nullのため、最後の非null unrateを探す）
  const latestUnrate = useMemo(() => {
    for (let i = sortedData.length - 1; i >= 0; i--) {
      if (sortedData[i]?.unrate != null) return sortedData[i]
    }
    return null
  }, [sortedData])

  // 最新のNAIRU値（四半期＋将来見通し。最後の非null値を探す）
  const latestNairu = useMemo(() => {
    for (let i = sortedData.length - 1; i >= 0; i--) {
      if (sortedData[i]?.nairu != null) return sortedData[i]
    }
    return null
  }, [sortedData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="NAIRU（自然失業率）/ 失業率" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="NAIRU（自然失業率）/ 失業率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const nextRelease = data.next_release

  return (
    <div id="nairu">
      <ChartContainer
        title="NAIRU（自然失業率）/ 失業率"
        showPeriodSelector={false}
        dataSource="FRED / CBO / BLS"
        sourceUrl="https://www.cbo.gov/about/products/major-recurring-reports"
        handbookId="nairu"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="失業率 (U-3)"
          value={latestUnrate?.unrate}
          subLabel="NAIRU（自然失業率）"
          subValue={latestNairu?.nairu}
          valueColor={COLORS.unrate}
          subValueColor={COLORS.nairu}
          date={latestUnrate?.date}
          nextRelease={nextRelease}
          format="number"
          unit="%"
          decimals={2}
        />

        {/* データ比較ボタン（単独行・右端） */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=nairu&s=unemployment_rate', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間セレクター（単独行） */}
        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        {/* 折れ線グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'unrate',
              color: COLORS.unrate,
              name: '失業率 (U-3)',
              hide: hiddenSeries.has('unrate'),
            },
            {
              dataKey: 'nairu',
              color: COLORS.nairu,
              name: 'NAIRU（自然失業率）',
              hide: hiddenSeries.has('nairu'),
            },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 1', 'dataMax + 1']}
          tooltipLabelFormatter={formatDateLabelJP}
          tooltipFormatter={createPercentFormatter(2, false)}
          showZeroLine={false}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
