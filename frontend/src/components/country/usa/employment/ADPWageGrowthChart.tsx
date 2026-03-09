/**
 * ADP賃金上昇率中央値チャートコンポーネント
 *
 * ADP Pay Insights データを使用して賃金上昇率を表示
 * - Job Changer: 転職者の賃金上昇率中央値
 * - Job Stayer: 在職者の賃金上昇率中央値
 *
 * 共通コンポーネントを使用
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { ADPWageGrowthData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabelJP,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface ADPWageGrowthChartProps {
  data: ADPWageGrowthData | null
}

// カラー設定
const COLORS = {
  job_changer: '#ff4d4f',  // 転職者 - 赤
  job_stayer: '#1890ff',   // 在職者 - 青
}

// 系列名（日本語）
const SERIES_NAMES = {
  job_changer: '転職者',
  job_stayer: '在職者',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ADPWageGrowthChart({ data }: ADPWageGrowthChartProps) {
  const [period, setPeriod] = useState<'default' | 'all' | number>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: period,
    defaultStartYear: 2020,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="ADP賃金上昇率中央値" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="ADP賃金上昇率中央値" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    return [
      { label: SERIES_NAMES.job_changer, value: latest.job_changer, color: COLORS.job_changer, format: 'number' as const, unit: '%', decimals: 1 },
      { label: SERIES_NAMES.job_stayer, value: latest.job_stayer, color: COLORS.job_stayer, format: 'number' as const, unit: '%', decimals: 1 },
    ]
  }

  return (
    <div id="adp-wage-growth">
      <ChartContainer
        title="ADP賃金上昇率中央値"
        showPeriodSelector={false}
        dataSource="ADP Pay Insights"
        sourceUrl="https://adpemploymentreport.com/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        {/* タブ切替 */}
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
                  {/* 期間セレクタ + 比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setPeriod} selectedPeriod={period} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=adp_employment', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 折れ線グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'job_changer',
                        color: COLORS.job_changer,
                        name: SERIES_NAMES.job_changer,
                        hide: hiddenSeries.has('job_changer'),
                      },
                      {
                        dataKey: 'job_stayer',
                        color: COLORS.job_stayer,
                        name: SERIES_NAMES.job_stayer,
                        hide: hiddenSeries.has('job_stayer'),
                      },
                    ]}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    tooltipLabelFormatter={formatDateLabelJP}
                    tooltipFormatter={(value: unknown, name: string) => [
                      `${(value as number).toFixed(1)}%`,
                      name,
                    ]}
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
                <MarketImpactTab indicatorId="adp_employment" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
