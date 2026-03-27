/**
 * 平均週労働時間チャートコンポーネント
 *
 * FRED AWHAETP（民間全体・全従業員）/ AWHNONAG（民間全体・生産労働者）/ AWHMAN（製造業・生産労働者）を表示
 *
 * 表示モード:
 * - 3系列の折れ線グラフ
 *
 * 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
 */
import { useState } from 'react'
import { Tabs, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { UsAverageWeeklyWorkingHoursData } from '../../../../hooks/useDashboardData'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface UsAverageWeeklyWorkingHoursChartProps {
  data: UsAverageWeeklyWorkingHoursData | null
}

// カラー設定
const COLOR_AWHAETP = '#1890ff'   // 青（民間全体・全従業員）
const COLOR_AWHNONAG = '#52c41a'  // 緑（民間全体・生産労働者）
const COLOR_AWHMAN = '#fa8c16'    // オレンジ（製造業・生産労働者）

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function UsAverageWeeklyWorkingHoursChart({ data }: UsAverageWeeklyWorkingHoursChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付順にソート
  const sortedData = useSortedData(data?.data || [])

  // 期間でフィルタリング
  const filteredData = usePeriodFiltering(sortedData, { selectedPeriod: currentPeriod })

  // 最新値と次回発表日
  const latest = data?.latest || null
  const nextRelease = data?.next_release || null

  // ローディング
  if (!data) {
    return <LoadingChart title="平均週労働時間" message="データを読み込み中..." />
  }

  // データなし
  if (!filteredData || filteredData.length === 0) {
    return (
      <ChartContainer
        title="平均週労働時間"
        showPeriodSelector={false}
        dataSource="FRED"
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="average-weekly-working-hours">
      <ChartContainer
        title="平均週労働時間"
        showPeriodSelector={false}
        dataSource="FRED - BLS"
        sourceUrl="https://www.bls.gov/ces/"
        handbookId="average-weekly-working-hours"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="民間全体（全従業員）"
          value={latest?.awhaetp != null ? `${latest.awhaetp.toFixed(1)}時間/週` : undefined}
          subLabel="製造業（生産労働者）"
          subValue={latest?.awhman != null ? `${latest.awhman.toFixed(1)}時間/週` : undefined}
          valueColor={COLOR_AWHAETP}
          subValueColor={COLOR_AWHMAN}
          date={latest?.date}
          nextRelease={nextRelease}
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
                  {/* データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=us_average_weekly_working_hours', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間セレクター */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* 3系列グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'awhaetp',
                        color: COLOR_AWHAETP,
                        name: '民間全体（全従業員）',
                        hide: hiddenSeries.has('awhaetp'),
                      },
                      {
                        dataKey: 'awhnonag',
                        color: COLOR_AWHNONAG,
                        name: '民間全体（生産労働者）',
                        hide: hiddenSeries.has('awhnonag'),
                      },
                      {
                        dataKey: 'awhman',
                        color: COLOR_AWHMAN,
                        name: '製造業（生産労働者）',
                        hide: hiddenSeries.has('awhman'),
                      },
                    ]}
                    yAxisFormatter={(v) => `${v.toFixed(1)}`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    showZeroLine={false}
                    onLegendClick={handleLegendClick}
                    tooltipValueFormatter={(v) => v != null ? `${v.toFixed(1)}時間` : 'N/A'}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="unemployment_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
