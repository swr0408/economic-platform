/**
 * 求人倍率チャートコンポーネント
 *
 * FRED データを使用して計算
 * - 求人倍率 = JOLTS求人件数（JTSJOL）/ 失業者数（UNEMPLOY）
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import { Tabs } from 'antd'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { JobOpeningsPerUnemployedData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TOOLTIP_STYLE,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface JobOpeningsPerUnemployedChartProps {
  data: JobOpeningsPerUnemployedData | null
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

interface TooltipPayload {
  name: string
  value: number
  color: string
  dataKey: string
  payload: {
    date: string
    value: number
    jolts: number
    unemployed: number
  }
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  const data = payload[0]?.payload

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatDateLabelJP(label || '')}
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 4,
          fontSize: 13,
          padding: '4px 12px',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
          <span
            style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: 2,
              backgroundColor: CHART_COLORS.primary,
              marginRight: 6,
            }}
          />
          求人倍率
        </span>
        <span style={{ fontWeight: 500, color: CHART_COLORS.primary }}>
          {data?.value?.toFixed(2) ?? '-'}
        </span>
      </div>
      {/* 内訳を表示 */}
      <div style={{ borderTop: '1px solid #eee', marginTop: 8, paddingTop: 8, fontSize: 12, color: '#666', padding: '8px 12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span>JOLTS求人件数</span>
          <span>{data?.jolts?.toLocaleString() ?? '-'}k</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>失業者数</span>
          <span>{data?.unemployed?.toLocaleString() ?? '-'}k</span>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function JobOpeningsPerUnemployedChart({ data }: JobOpeningsPerUnemployedChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="求人倍率" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="求人倍率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 次回発表日を計算（JOLTSとEmpsitのうち早い方）
  const getNextReleaseInfo = () => {
    if (!nextRelease) return null

    const joltsDate = nextRelease.jolts?.date
    const empsitDate = nextRelease.empsit?.date

    if (joltsDate && empsitDate) {
      // 両方ある場合は早い方を表示
      if (joltsDate < empsitDate) {
        return nextRelease.jolts
      }
      return nextRelease.empsit
    }

    return nextRelease.jolts || nextRelease.empsit || null
  }

  const nextReleaseInfo = getNextReleaseInfo()

  // 最新値の表示用アイテム
  const latestItems = latest ? [
    { label: '求人倍率', value: latest.value, color: CHART_COLORS.primary, format: 'number' as const, unit: '', decimals: 2 },
  ] : []

  return (
    <div id="job-openings-per-unemployed">
      <ChartContainer
        title="求人倍率"
        showPeriodSelector={false}
        dataSource="FRED / BLS"
        sourceUrl=""
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latest?.date}
          nextRelease={nextReleaseInfo}
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 期間セレクター */}
                  <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

                  {/* チャート */}
                  <ResponsiveContainer width="100%" height={450}>
                    <LineChart data={filteredData} margin={CHART_MARGIN}>
                      <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                      <XAxis
                        dataKey="date"
                        tickFormatter={formatDateLabel}
                        tick={AXIS_STYLE.tick}
                        interval={AXIS_STYLE.interval}
                      />
                      <YAxis
                        tick={AXIS_STYLE.tick}
                        tickFormatter={(v) => v.toFixed(1)}
                        domain={['dataMin - 0.1', 'dataMax + 0.1']}
                        label={{
                          angle: -90,
                          position: 'insideLeft',
                          dy: 30,
                          style: { fontSize: 11, fill: '#666' }
                        }}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend />

                      {/* 求人倍率 */}
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke={CHART_COLORS.primary}
                        strokeWidth={2}
                        dot={false}
                        name="求人倍率"
                        isAnimationActive={false}
                        connectNulls={true}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="jolts_openings" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
