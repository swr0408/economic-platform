/**
 * 中国 失業率（Unemployment Rate）チャートコンポーネント
 *
 * 2系列:
 * - total: 全国城鎮調査失業率 (%) — 左Y軸
 * - youth: 16-24歳若年層失業率 (%) — 右Y軸
 *
 * データソース: National Bureau of Statistics (NBS)
 *
 * FMPマッピング: cn_unemployment_rate → "Unemployment Rate"
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { CnUnemploymentRateData, CnUnemploymentRateItem } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnUnemploymentRateData | null
}

interface ChartDataPoint {
  date: string
  total: number | null
  youth: number | null
}

const COLOR_TOTAL = '#1890ff'   // 青 - 全体失業率（左Y軸）
const COLOR_YOUTH = '#DC143C'   // 赤 - 若年層失業率（右Y軸）

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

export default function CnUnemploymentRateChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.data) return []
    return data.data.map((d: CnUnemploymentRateItem) => ({
      date: d.date,
      total: d.total,
      youth: d.youth,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)
  const hasData = sortedData.length > 0

  // 系列ごとに最新の非NULL値を取得（youth は年齢別の発表ラグで total より遅れるため、
  // 最新行(total基準)の youth が空でも、直近で値のある月を表示する）
  const latestTotal = useMemo(() => {
    const withVal = sortedData.filter((d) => d.total != null)
    return withVal.length ? withVal[withVal.length - 1] : null
  }, [sortedData])
  const latestYouth = useMemo(() => {
    const withVal = sortedData.filter((d) => d.youth != null)
    return withVal.length ? withVal[withVal.length - 1] : null
  }, [sortedData])

  if (data === null) {
    return <LoadingChart title="失業率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="失業率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // youth の最新月が total と異なる場合はラベルに月を併記（単一日付表示の誤解防止）
  const youthLabel =
    latestYouth && latestTotal && latestYouth.date !== latestTotal.date
      ? `若年層（16-24歳・${formatDateFull(latestYouth.date)}）`
      : '若年層（16-24歳）'

  return (
    <div id="unemployment">
      <ChartContainer
        title="失業率"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="NBS"
        sourceUrl="https://data.stats.gov.cn/dg/website/page.html#/pc/national/home"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            { label: '全国城鎮調査失業率', value: latestTotal?.total ?? null, color: COLOR_TOTAL, format: 'percent', decimals: 1 },
            { label: youthLabel, value: latestYouth?.youth ?? null, color: COLOR_YOUTH, format: 'percent', decimals: 1 },
          ]}
          date={latestTotal?.date}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ?? null}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          size="small"
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <TimeSeriesView
                  data={sortedData}
                  hiddenSeries={hiddenSeries}
                  handleLegendClick={handleLegendClick}
                />
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cn_unemployment_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}

// =============================================================================
// 時系列ビュー
// =============================================================================

function TimeSeriesView({
  data,
  hiddenSeries,
  handleLegendClick,
}: {
  data: ChartDataPoint[]
  hiddenSeries: Set<string>
  handleLegendClick: (dataKey: string) => void
}) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(10)
  const filteredData = usePeriodFiltering(data, {
    selectedPeriod,
    defaultStartYear: 2018,
  })

  return (
    <>
      {/* データ比較ボタン（右寄せ） */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=cn_unemployment_rate', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector
        onPeriodChange={(p: PeriodValue) => setSelectedPeriod(p)}
        selectedPeriod={selectedPeriod}
      />

      {/* グラフ（2系列折れ線：左Y軸=全体、右Y軸=若年層） */}
      <StandardLineChart
        data={filteredData}
        lines={[
          { dataKey: 'total', color: COLOR_TOTAL, name: '全国城鎮調査失業率', hide: hiddenSeries.has('total'), yAxisId: 'left' },
          { dataKey: 'youth', color: COLOR_YOUTH, name: '若年層失業率（16-24歳）', hide: hiddenSeries.has('youth'), yAxisId: 'right' },
        ]}
        yAxisFormatter={(v) => `${v.toFixed(1)}%`}
        rightYAxisFormatter={(v) => `${v.toFixed(1)}%`}
        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
        xAxisFormatter={formatDateLabel}
        tooltipLabelFormatter={formatDateFull}
        tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
        onLegendClick={handleLegendClick}
      />
    </>
  )
}
