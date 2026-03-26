/**
 * カナダ経常収支対GDP比チャートコンポーネント
 *
 * 経常収支対GDP比（Current Account to GDP Ratio）の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 36-10-0018-01 (経常収支)
 * - Statistics Canada Table 36-10-0104-01 (GDP)
 *
 * 発表スケジュール:
 * - 四半期ごと
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { CaCurrentAccountGdpRatioData } from '../../../../hooks/useDashboardData'

interface CanadaCurrentAccountGdpRatioChartProps {
  data: CaCurrentAccountGdpRatioData | null
}

interface ChartDataItem {
  date: string
  value: number
  current_account?: number
  gdp?: number
  [key: string]: string | number | boolean | null | undefined
}

export default function CanadaCurrentAccountGdpRatioChart({ data }: CanadaCurrentAccountGdpRatioChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(20)

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChartDataItem[] = data.data.map((item) => ({
      date: item.date,
      value: item.value ?? 0,
      current_account: item.current_account,
      gdp: item.gdp,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2000,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="経常収支対GDP比" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="経常収支対GDP比" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ca-current-account-gdp-ratio-chart">
      <ChartContainer
        title="経常収支対GDP比"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/international_trade"
        handbookId="current-account"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="経常収支対GDP比"
          value={latestValue?.value}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="percent"
          decimals={1}
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
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=ca_current_account_gdp_ratio`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  <ZoomableChart
                    data={filteredData}
                    dataKey="value"
                    name="経常収支対GDP比"
                    color={CHART_COLORS.primary}
                    height={450}
                    tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                    tooltipFormatter={(v: number) => `${v.toFixed(1)}%`}
                    showZeroLine={true}
                    zeroLineValue={0}
                  />
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
