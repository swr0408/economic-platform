/**
 * 中国 NBS PMI ヘッドラインチャートコンポーネント
 *
 * 3系列: 総合PMI + 製造業PMI + 非製造業PMI
 * 折れ線グラフ（50ラインをゼロ線として表示）
 *
 * データソース: NBS（国家統計局）
 *
 * FMPマッピング: cn_national_bureau_of_Statistics_pmi
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type {
  CnPmiData,
  CnPmiHeadlineItem,
} from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnPmiData | null
}

interface ChartDataPoint {
  date: string
  manufacturing: number | null
  non_manufacturing: number | null
  composite: number | null
}

const COLOR_MFG = '#1890ff'    // 青（製造業）
const COLOR_NMF = '#52c41a'    // 緑（非製造業）
const COLOR_COMP = '#fa541c'   // オレンジ（総合）

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

export default function CnPmiHeadlineChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ変換
  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.headline?.data) return []
    return data.headline.data.map((d: CnPmiHeadlineItem) => ({
      date: d.date,
      manufacturing: d.manufacturing,
      non_manufacturing: d.non_manufacturing,
      composite: d.composite,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2017,
  })

  if (!data?.headline) {
    return (
      <div id="pmi">
        <LoadingChart title="NBS PMI" />
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div id="pmi">
        <ChartContainer title="NBS PMI">
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = data.headline.latest

  return (
    <div id="pmi">
      <ChartContainer
        title="NBS PMI"
        showDataSource={true}
        dataSource="NBS"
        sourceUrl="https://www.stats.gov.cn/english/PressRelease/"
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 最新値ボックス */}
                  <div style={{ ...LATEST_VALUE_BOX_STYLE, justifyContent: 'space-between', alignItems: 'center' }}>
                    {/* 左側: 最新値 */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                      {latest?.date && (
                        <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                          {formatDateFull(latest.date)}
                        </span>
                      )}
                      <_LatestBox
                        label="総合"
                        value={latest?.composite}
                        color={COLOR_COMP}
                        hidden={hiddenSeries.has('composite')}
                        onClick={() => handleLegendClick('composite')}
                      />
                      <_LatestBox
                        label="製造業"
                        value={latest?.manufacturing}
                        color={COLOR_MFG}
                        hidden={hiddenSeries.has('manufacturing')}
                        onClick={() => handleLegendClick('manufacturing')}
                      />
                      <_LatestBox
                        label="非製造業"
                        value={latest?.non_manufacturing}
                        color={COLOR_NMF}
                        hidden={hiddenSeries.has('non_manufacturing')}
                        onClick={() => handleLegendClick('non_manufacturing')}
                      />
                    </div>
                    {/* 右側: 次回発表 */}
                    {data.next_release && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: TEXT_COLORS.secondary }}>
                        <CalendarOutlined />
                        <span>次回発表: {data.next_release.date}{data.next_release.time_jst && ` ${data.next_release.time_jst} JST`}</span>
                      </div>
                    )}
                  </div>

                  {/* データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_pmi_manufacturing', '_blank')}
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

                  {/* チャート */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'composite', color: COLOR_COMP, name: '総合PMI', hide: hiddenSeries.has('composite') },
                      { dataKey: 'manufacturing', color: COLOR_MFG, name: '製造業PMI', hide: hiddenSeries.has('manufacturing') },
                      { dataKey: 'non_manufacturing', color: COLOR_NMF, name: '非製造業PMI', hide: hiddenSeries.has('non_manufacturing') },
                    ]}
                    xAxisFormatter={formatDateLabel}
                    yAxisFormatter={(v: number) => `${v}`}
                    yDomain={['dataMin - 1', 'dataMax + 1']}
                    tooltipLabelFormatter={formatDateFull}
                    tooltipValueFormatter={(v: number) => `${v.toFixed(1)}`}
                    showFiftyLine={true}
                    showZeroLine={false}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cn_national_bureau_of_Statistics_pmi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}

// 最新値ボックスのサブコンポーネント
function _LatestBox({
  label,
  value,
  color,
  hidden,
  onClick,
}: {
  label: string
  value: number | null | undefined
  color: string
  hidden: boolean
  onClick: () => void
}) {
  return (
    <span
      onClick={onClick}
      style={{
        cursor: 'pointer',
        opacity: hidden ? 0.3 : 1,
        marginRight: 16,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: 10,
          height: 10,
          borderRadius: '50%',
          backgroundColor: color,
        }}
      />
      <span style={{ fontSize: 12, color: '#666' }}>{label}</span>
      <span style={{ fontSize: 18, fontWeight: 700, color }}>
        {value != null ? value.toFixed(1) : '—'}
      </span>
    </span>
  )
}
