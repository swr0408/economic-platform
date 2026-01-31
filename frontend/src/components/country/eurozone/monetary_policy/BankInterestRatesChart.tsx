/**
 * ECB Bank Interest Rates チャートコンポーネント
 *
 * 銀行金利の推移を表示
 * - 企業向け新規融資金利 (Loans to corporations - new business)
 * - 住宅ローン新規金利 (Loans to households for house purchase - new business)
 *
 * データソース:
 * - European Central Bank (MIR dataset)
 *
 * 発表スケジュール:
 * - 月次（ECBカレンダーより取得）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, useHiddenSeries, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, LatestValueBox, StandardLineChart } from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { ECBBankInterestRatesData } from '../../../../hooks/useDashboardData'

interface BankInterestRatesChartProps {
  data: ECBBankInterestRatesData | null
}

export default function BankInterestRatesChart({ data }: BankInterestRatesChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 企業向けデータをチャート用に変換
  const corporationsChartData = useMemo(() => {
    if (!data?.corporations?.data || data.corporations.data.length === 0) return []

    return data.corporations.data
      .filter((item) => item.value !== null && item.value !== undefined)
      .map((item) => ({
        date: item.date,
        corporations: item.value,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 住宅ローンデータをチャート用に変換
  const housingChartData = useMemo(() => {
    if (!data?.housing?.data || data.housing.data.length === 0) return []

    return data.housing.data
      .filter((item) => item.value !== null && item.value !== undefined)
      .map((item) => ({
        date: item.date,
        housing: item.value,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 結合データ（2本表示用）
  const combinedChartData = useMemo(() => {
    const dateMap = new Map<string, { date: string; corporations?: number; housing?: number }>()

    corporationsChartData.forEach((item) => {
      dateMap.set(item.date, { date: item.date, corporations: item.corporations })
    })

    housingChartData.forEach((item) => {
      const existing = dateMap.get(item.date)
      if (existing) {
        existing.housing = item.housing
      } else {
        dateMap.set(item.date, { date: item.date, housing: item.housing })
      }
    })

    return Array.from(dateMap.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )
  }, [corporationsChartData, housingChartData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(combinedChartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  const hasCorporationsData = corporationsChartData.length > 0
  const hasHousingData = housingChartData.length > 0
  const hasData = hasCorporationsData || hasHousingData

  // 最新値を取得
  const corporationsLatestValue = data?.corporations?.latest
  const housingLatestValue = data?.housing?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="銀行金利" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="銀行金利" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-bank-interest-rates-chart">
      <ChartContainer
        title="銀行金利（MIR）"
        showPeriodSelector={false}
        dataSource="European Central Bank"
        sourceUrl="https://www.ecb.europa.eu/press/stats/mfi/html/index.en.html"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '企業向け',
              value: corporationsLatestValue?.value,
              color: CHART_COLORS.primary,
              format: 'percent',
              decimals: 2,
            },
            {
              label: '住宅ローン',
              value: housingLatestValue?.value,
              color: CHART_COLORS.orange,
              format: 'percent',
              decimals: 2,
            },
          ]}
          date={corporationsLatestValue?.date || housingLatestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ecb_bank_interest_rates_corporations', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'corporations', color: CHART_COLORS.primary, name: '企業向け', hide: hiddenSeries.has('corporations') },
            { dataKey: 'housing', color: CHART_COLORS.orange, name: '住宅ローン', hide: hiddenSeries.has('housing') },
          ]}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
