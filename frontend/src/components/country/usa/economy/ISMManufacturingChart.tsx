import { useState, useMemo, useCallback, useEffect } from 'react'
import { Space, Tabs } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { ISMManufacturingData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { usePeriodFiltering, getFrequencyFormatters, type PeriodType } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../common/ChartComponents'

// オーバーレイ関連
import { useIndicatorOverlay } from '../../../../hooks/useIndicatorOverlay'
import { useOverlayIndicatorData } from '../../../../hooks/useOverlayData'
import { ComparePopover } from '../../../charts/ComparePopover'
import { OverlayChipList } from '../../../charts/OverlayChip'
import type { OverlayIndicator } from '../../../../constants/overlayConfig'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

interface ISMManufacturingChartProps {
  data: ISMManufacturingData | null
}

export default function ISMManufacturingChart({ data }: ISMManufacturingChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [pendingIndicator, setPendingIndicator] = useState<OverlayIndicator | null>(null)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // データを日付昇順にソートしてDataPoint型に変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
  }, [data])

  // オーバーレイ管理フック（メイン指標は月次）
  const {
    selectedOverlays,
    mergedData,
    additionalLines,
    rightYAxes,
    overlayChips,
    baseFrequency,
    addOverlay,
    clearAllOverlays,
    hasOverlays,
  } = useIndicatorOverlay('ism_manufacturing', chartData, 'monthly')

  // 頻度に応じたフォーマッターを取得
  const { xAxisFormatter, tooltipFormatter: tooltipLabelFormatter } = getFrequencyFormatters(baseFrequency)

  // 選択中の指標のデータを取得
  const { data: overlayData, isLoading: isLoadingOverlay, indicatorId: fetchedIndicatorId, isSuccess } = useOverlayIndicatorData(pendingIndicator)

  // オーバーレイデータが取得できたら追加
  useEffect(() => {
    console.log('[ISMChart] pendingIndicator:', pendingIndicator?.id)
    console.log('[ISMChart] fetchedIndicatorId:', fetchedIndicatorId)
    console.log('[ISMChart] overlayData:', overlayData?.length)
    console.log('[ISMChart] isLoadingOverlay:', isLoadingOverlay)
    console.log('[ISMChart] isSuccess:', isSuccess)

    // 取得したデータが現在のpendingIndicatorと一致することを確認
    if (pendingIndicator &&
        fetchedIndicatorId === pendingIndicator.id &&
        isSuccess &&
        !isLoadingOverlay &&
        overlayData &&
        overlayData.length > 0) {
      console.log('[ISMChart] Adding overlay:', pendingIndicator.id, 'with', overlayData.length, 'points')
      addOverlay(pendingIndicator, overlayData)
      setPendingIndicator(null)
    }
  }, [pendingIndicator, overlayData, addOverlay, isLoadingOverlay, fetchedIndicatorId, isSuccess])

  // 指標選択ハンドラ
  const handleSelectIndicator = useCallback((indicator: OverlayIndicator) => {
    setPendingIndicator(indicator)
  }, [])

  // 期間フィルタリング（マージ済みデータに適用）
  const filteredData = usePeriodFiltering(hasOverlays ? mergedData : chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="ISM製造業景況指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ISM製造業景況指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatValue = (value: number) => {
    return value.toFixed(1)
  }

  // グラフの色
  const CHART_COLOR = '#1890ff' // 青

  // additionalLinesに破線スタイルを追加（折れ線グラフ）
  const enhancedAdditionalLines = additionalLines.map(line => ({
    ...line,
    type: 'monotone' as const,
    strokeDasharray: '5 5',
  }))

  return (
    <div id="ism-manufacturing-chart">
      <ChartContainer
        title="ISM製造業景況指数"
        showPeriodSelector={false}
        dataSource="ISM"
        sourceUrl="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={data.latest?.value}
          valueColor={CHART_COLOR}
          date={data.latest?.date}
          nextRelease={data.next_release}
          format="number"
          decimals={1}
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
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Space>
                      <ComparePopover
                        selectedIndicatorIds={selectedOverlays.map(o => o.indicator.id)}
                        mainIndicatorId="ism_manufacturing"
                        onSelect={handleSelectIndicator}
                        maxSelections={3}
                        disabled={isLoadingOverlay}
                      />
                    </Space>
                  </div>

                  {/* オーバーレイチップ */}
                  {hasOverlays && (
                    <OverlayChipList
                      chips={overlayChips}
                      showClearAll={true}
                      onClearAll={clearAllOverlays}
                    />
                  )}

                  <ZoomableChart
                    data={filteredData}
                    dataKey="value"
                    color={CHART_COLOR}
                    name="ISM製造業景況指数"
                    height={450}
                    tickFormatter={formatValue}
                    tooltipFormatter={formatValue}
                    tooltipLabelFormatter={tooltipLabelFormatter}
                    xAxisTickFormatter={xAxisFormatter}
                    enableDynamicTicks={true}
                    showZeroLine={false}
                    showFiftyLine={true}
                    fiftyLineValue={50}
                    connectNulls={true}
                    hideLegend={!hasOverlays}
                    additionalLines={enhancedAdditionalLines}
                    rightYAxes={rightYAxes?.map((axis) => ({
                      ...axis,
                      tickFormatter: formatValue,
                    }))}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ism_manufacturing" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
