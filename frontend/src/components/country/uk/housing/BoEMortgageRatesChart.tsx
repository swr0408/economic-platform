/**
 * 住宅ローン金利チャートコンポーネント
 *
 * データ:
 * - CFMZ6K6: 住宅ローン残高ベース実効金利（Weighted average interest rate on all dwelling-secured loans）
 * - CFMZ6JV: 新規固定住宅ローン実効金利（Interest rate on new fixed-rate mortgage advances）
 * - IUMTLMV: 住宅ローン標準変動金利・SVR（Revert-to-rate mortgage to households）
 *
 * 表示モード:
 * - 3系列の折れ線グラフ
 *
 * データソース:
 * - CSV: Bank of England統計データベース
 *
 * 発表スケジュール:
 * - 月次（毎月5日～11日頃）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip, Tabs } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  formatDateLabel,
  formatDateLabelJP,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { BoEMortgageRatesData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

interface BoEMortgageRatesChartProps {
  data: BoEMortgageRatesData | null
}

interface ChartDataPoint {
  date: string
  cfmz6k6: number | null
  cfmz6jv: number | null
  iumtlmv: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  cfmz6k6: '#1890ff', // 青 - 住宅ローン残高
  cfmz6jv: '#52c41a', // 緑 - 新規住宅ローン
  iumtlmv: '#fa8c16', // オレンジ - 変動金利
}

// 系列名
const SERIES_NAMES = {
  cfmz6k6: '残高ベース実効金利',
  cfmz6jv: '新規固定実効金利',
  iumtlmv: '標準変動金利（SVR）',
}

export default function BoEMortgageRatesChart({ data }: BoEMortgageRatesChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  // propsのデータをチャート用に変換（3系列をマージ）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.cfmz6k6 && !data?.cfmz6jv && !data?.iumtlmv) return []

    // 各系列をMapに変換
    const cfmz6k6Map = new Map<string, number | null>()
    const cfmz6jvMap = new Map<string, number | null>()
    const iumtlmvMap = new Map<string, number | null>()

    if (data?.cfmz6k6) {
      for (const point of data.cfmz6k6) {
        cfmz6k6Map.set(point.date, point.value)
      }
    }

    if (data?.cfmz6jv) {
      for (const point of data.cfmz6jv) {
        cfmz6jvMap.set(point.date, point.value)
      }
    }

    if (data?.iumtlmv) {
      for (const point of data.iumtlmv) {
        iumtlmvMap.set(point.date, point.value)
      }
    }

    // 全日付をマージ
    const allDates = new Set([...cfmz6k6Map.keys(), ...cfmz6jvMap.keys(), ...iumtlmvMap.keys()])
    const merged: ChartDataPoint[] = []

    for (const date of allDates) {
      merged.push({
        date,
        cfmz6k6: cfmz6k6Map.get(date) ?? null,
        cfmz6jv: cfmz6jvMap.get(date) ?? null,
        iumtlmv: iumtlmvMap.get(date) ?? null,
      })
    }

    return merged
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestCfmz6k6 = data?.latest_cfmz6k6
  const latestCfmz6jv = data?.latest_cfmz6jv
  const latestIumtlmv = data?.latest_iumtlmv
  const nextRelease = data?.next_release ? { date: data.next_release } : null

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="住宅ローン金利" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="住宅ローン金利" showPeriodSelector={false} showDataSource={false} handbookId="boe-mortgage-rates">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    const items = []

    if (latestCfmz6k6?.value !== null && latestCfmz6k6?.value !== undefined) {
      items.push({
        label: '残高ベース実効',
        value: `${latestCfmz6k6.value.toFixed(2)}%`,
        color: COLORS.cfmz6k6,
      })
    }

    if (latestCfmz6jv?.value !== null && latestCfmz6jv?.value !== undefined) {
      items.push({
        label: '新規固定実効',
        value: `${latestCfmz6jv.value.toFixed(2)}%`,
        color: COLORS.cfmz6jv,
      })
    }

    if (latestIumtlmv?.value !== null && latestIumtlmv?.value !== undefined) {
      items.push({
        label: 'SVR',
        value: `${latestIumtlmv.value.toFixed(2)}%`,
        color: COLORS.iumtlmv,
      })
    }

    return items
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_boe_mortgage_rates_cfmz6k6&s=uk_boe_mortgage_rates_cfmz6jv&s=uk_boe_mortgage_rates_iumtlmv', '_blank')
  }

  return (
    <div id="uk-boe-mortgage-rates-chart">
      <ChartContainer
        title="住宅ローン金利"
        showPeriodSelector={false}
        dataSource="Bank of England"
        sourceUrl="https://www.bankofengland.co.uk/statistics"
        handbookId="boe-mortgage-rates"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latestCfmz6k6?.date || latestCfmz6jv?.date}
          nextRelease={nextRelease}
        />

        <Tabs
          defaultActiveKey="chart"
          items={[
            {
              key: 'chart',
              label: '時系列',
              children: (
                <>
                  {/* 期間選択とデータ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <AntTooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={handleCompare}
                      >
                        データ比較
                      </Button>
                    </AntTooltip>
                  </div>

                  {/* 折れ線グラフ（3系列） */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'cfmz6k6',
                        color: COLORS.cfmz6k6,
                        name: SERIES_NAMES.cfmz6k6,
                      },
                      {
                        dataKey: 'cfmz6jv',
                        color: COLORS.cfmz6jv,
                        name: SERIES_NAMES.cfmz6jv,
                      },
                      {
                        dataKey: 'iumtlmv',
                        color: COLORS.iumtlmv,
                        name: SERIES_NAMES.iumtlmv,
                      },
                    ]}
                    xAxisFormatter={formatDateLabel}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                    tooltipLabelFormatter={formatDateLabelJP}
                    yDomain={['dataMin - 0.2', 'dataMax + 0.2']}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="boe_mortgage_rates" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
