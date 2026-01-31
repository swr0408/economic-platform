/**
 * ECB調整済貸出チャートコンポーネント
 *
 * ユーロ圏の調整済貸出（前年比）の推移を表示
 * - 非金融法人向け (NFCs)
 * - 家計向け（総合）
 * - 家計向け（住宅購入）
 *
 * データソース:
 * - European Central Bank (BSI - Balance Sheet Items)
 *
 * 発表スケジュール:
 * - 月次（ECB統計カレンダーに基づく）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import { usePeriodFiltering, useHiddenSeries, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, NextReleaseDisplay, StandardLineChart } from '../../usa/common/ChartComponents'
import { CHART_COLORS, TEXT_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

// 型定義
import type { ECBAdjustedLoansData } from '../../../../hooks/useDashboardData'

interface AdjustedLoansChartProps {
  data: ECBAdjustedLoansData | null
}

// 系列設定
const SERIES_CONFIG = [
  { key: 'nfc', name: '非金融法人向け（企業向け）', color: CHART_COLORS.primary },
  { key: 'households', name: '家計向け（総合）', color: CHART_COLORS.orange },
  { key: 'housing', name: '家計向け（住宅購入）', color: CHART_COLORS.cyan },
] as const

type SeriesKey = 'nfc' | 'households' | 'housing'

export default function AdjustedLoansChart({ data }: AdjustedLoansChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  // 全系列のデータを結合してチャート用に変換
  const chartData = useMemo(() => {
    if (!data) return []

    // 全ての日付を収集
    const dateSet = new Set<string>()
    const nfcMap = new Map<string, number>()
    const householdsMap = new Map<string, number>()
    const housingMap = new Map<string, number>()

    // NFCデータ
    if (data.nfc?.data) {
      data.nfc.data.forEach((item) => {
        if (item.date && item.value !== null && item.value !== undefined) {
          dateSet.add(item.date)
          nfcMap.set(item.date, item.value)
        }
      })
    }

    // 家計向け（総合）データ
    if (data.households?.data) {
      data.households.data.forEach((item) => {
        if (item.date && item.value !== null && item.value !== undefined) {
          dateSet.add(item.date)
          householdsMap.set(item.date, item.value)
        }
      })
    }

    // 家計向け（住宅購入）データ
    if (data.housing?.data) {
      data.housing.data.forEach((item) => {
        if (item.date && item.value !== null && item.value !== undefined) {
          dateSet.add(item.date)
          housingMap.set(item.date, item.value)
        }
      })
    }

    // 日付でソートして結合
    const sortedDates = Array.from(dateSet).sort()

    return sortedDates.map((date) => ({
      date,
      nfc: nfcMap.get(date) ?? null,
      households: householdsMap.get(date) ?? null,
      housing: housingMap.get(date) ?? null,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  const hasNfcData = (data?.nfc?.data?.length ?? 0) > 0
  const hasHouseholdsData = (data?.households?.data?.length ?? 0) > 0
  const hasHousingData = (data?.housing?.data?.length ?? 0) > 0
  const hasData = hasNfcData || hasHouseholdsData || hasHousingData

  // 最新値を取得
  const nfcLatestValue = data?.nfc?.latest
  const householdsLatestValue = data?.households?.latest
  const housingLatestValue = data?.housing?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="調整済貸出" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="調整済貸出" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-adjusted-loans-chart">
      <ChartContainer
        title="貸出動向（ユーロ圏・BSI）"
        showPeriodSelector={false}
        dataSource="European Central Bank"
        sourceUrl="https://www.bis.org/statistics/rppb2510.htm?utm"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
            {hasNfcData && (
              <div>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>企業向け: </span>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 'bold',
                    color: (nfcLatestValue?.value ?? 0) >= 0 ? CHART_COLORS.primary : TEXT_COLORS.negative,
                  }}
                >
                  {nfcLatestValue?.value?.toFixed(1)}%
                </span>
              </div>
            )}
            {hasHouseholdsData && (
              <div>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>家計向け: </span>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 'bold',
                    color: (householdsLatestValue?.value ?? 0) >= 0 ? CHART_COLORS.orange : TEXT_COLORS.negative,
                  }}
                >
                  {householdsLatestValue?.value?.toFixed(1)}%
                </span>
              </div>
            )}
            {hasHousingData && (
              <div>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>住宅向け: </span>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 'bold',
                    color: (housingLatestValue?.value ?? 0) >= 0 ? CHART_COLORS.cyan : TEXT_COLORS.negative,
                  }}
                >
                  {housingLatestValue?.value?.toFixed(1)}%
                </span>
              </div>
            )}
            <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary }}>
              ({nfcLatestValue?.date ?? householdsLatestValue?.date ?? housingLatestValue?.date})
            </span>
          </div>
          <NextReleaseDisplay nextRelease={data.next_release} />
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ecb_adjusted_loans_nfc&s=ecb_adjusted_loans_households&s=ecb_adjusted_loans_housing', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  <StandardLineChart
                    data={filteredData}
                    lines={SERIES_CONFIG.map((series) => ({
                      dataKey: series.key,
                      color: series.color,
                      name: series.name,
                      hide: hiddenSeries.has(series.key as SeriesKey),
                    }))}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                    showZeroLine={true}
                    yDomain={['dataMin - 1', 'dataMax + 1']}
                    onLegendClick={(dataKey) => handleLegendClick(dataKey as SeriesKey)}
                  />
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ecb_adjusted_loans" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
