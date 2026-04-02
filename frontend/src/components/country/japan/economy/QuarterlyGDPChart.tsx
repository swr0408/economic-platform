/**
 * 日本四半期GDP成長率チャート
 *
 * データソース: 内閣府
 * 更新: 四半期毎（速報・改定値）
 *
 * タブ構成:
 * 1. 時系列（前期比グラフ / 前期比年率グラフ / 前年比グラフ）
 * 2. マーケットインパクト
 */
import { useState, useEffect, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// USA共通モジュールを流用
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useQuarterlyTableData,
  formatPercent,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  fetchQuarterlyGDPQoQ,
  fetchQuarterlyGDPQoQAnnualized,
  fetchQuarterlyGDPYoY,
  type QuarterlyGDPData,
} from '../../../../utils/japan/quarterlyGDPApi'

// チャートデータ型
interface GDPChartData {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

// 指標種別
type DataKind = 'qoq' | 'qoq_annualized' | 'yoy'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'qoq', label: '前期比' },
  { mode: 'qoq_annualized', label: '前期比年率' },
  { mode: 'yoy', label: '前年比' },
]

// 表示モード（チャート/ヒートマップ）
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// グラフの色
const COLORS = {
  qoq: '#10b981',  // 緑
  qoq_annualized: '#f59e0b',  // オレンジ
  yoy: '#3b82f6',  // 青
}

const QuarterlyGDPChart: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [qoqData, setQoqData] = useState<QuarterlyGDPData | null>(null)
  const [qoqAnnualizedData, setQoqAnnualizedData] = useState<QuarterlyGDPData | null>(null)
  const [yoyData, setYoyData] = useState<QuarterlyGDPData | null>(null)
  const [dataKind, setDataKind] = useState<DataKind>('qoq')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // 指標種別毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    qoq: 20,
    qoq_annualized: 20,
    yoy: 20,
  })

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const [qoq, qoqAnn, yoy] = await Promise.all([
          fetchQuarterlyGDPQoQ(),
          fetchQuarterlyGDPQoQAnnualized(),
          fetchQuarterlyGDPYoY(),
        ])
        setQoqData(qoq)
        setQoqAnnualizedData(qoqAnn)
        setYoyData(yoy)
      } catch (err) {
        console.error('Error fetching GDP data:', err)
        setError('データの取得に失敗しました')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // 四半期日付フォーマット（2024-Q1 -> 2024/Q1）
  const formatQuarterLabel = (dateStr: string): string => {
    try {
      const [year, quarter] = dateStr.split('-')
      return `${year}/${quarter}`
    } catch {
      return dateStr
    }
  }

  // 四半期日付をDateオブジェクトに変換
  const parseQuarterToDate = (dateStr: string): Date => {
    const [year, quarter] = dateStr.split('-')
    const quarterNum = parseInt(quarter.replace('Q', ''))
    const month = (quarterNum - 1) * 3
    return new Date(parseInt(year), month, 1)
  }

  // QoQチャートデータを整形
  const qoqChartData = useMemo<GDPChartData[]>(() => {
    if (!qoqData?.data || qoqData.data.length === 0) return []

    return qoqData.data
      .map((item) => ({
        date: parseQuarterToDate(item.date).toISOString(),
        value: item.value,
        originalDate: item.date,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [qoqData])

  // QoQ Annualized チャートデータを整形
  const qoqAnnualizedChartData = useMemo<GDPChartData[]>(() => {
    if (!qoqAnnualizedData?.data || qoqAnnualizedData.data.length === 0) return []

    return qoqAnnualizedData.data
      .map((item) => ({
        date: parseQuarterToDate(item.date).toISOString(),
        value: item.value,
        originalDate: item.date,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [qoqAnnualizedData])

  // YoYチャートデータを整形
  const yoyChartData = useMemo<GDPChartData[]>(() => {
    if (!yoyData?.data || yoyData.data.length === 0) return []

    return yoyData.data
      .map((item) => ({
        date: parseQuarterToDate(item.date).toISOString(),
        value: item.value,
        originalDate: item.date,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [yoyData])

  // formatPercent共通関数を使用（小数点2桁）
  const formatPercentage = (value: number) => formatPercent(value, 2)

  // 期間フィルタリング
  const filteredQoQData = usePeriodFiltering(qoqChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const filteredQoQAnnualizedData = usePeriodFiltering(qoqAnnualizedChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const filteredYoYData = usePeriodFiltering(yoyChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 四半期テーブルデータ（ヒートマップ用）
  const qoqTableData = useQuarterlyTableData(qoqChartData, (item) => item.value)

  const hasData = qoqChartData.length > 0 || qoqAnnualizedChartData.length > 0 || yoyChartData.length > 0

  if (loading) {
    return <LoadingChart title="GDP成長率" />
  }

  if (error) {
    return (
      <ChartContainer title="GDP成長率" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestQoQ = qoqData?.latest
  const latestQoQAnnualized = qoqAnnualizedData?.latest
  const latestYoY = yoyData?.latest

  // 次回発表日時
  const nextRelease = qoqData?.next_release
    ? { date: qoqData.next_release }
    : null

  // 現在のビューモードに応じた最新値を取得
  const getCurrentLabel = () => {
    switch (dataKind) {
      case 'qoq': return '前期比'
      case 'qoq_annualized': return '前期比年率'
      case 'yoy': return '前年比'
      default: return '前期比年率'
    }
  }

  const getCurrentLatest = () => {
    switch (dataKind) {
      case 'qoq': return latestQoQ
      case 'qoq_annualized': return latestQoQAnnualized
      case 'yoy': return latestYoY
      default: return latestQoQAnnualized
    }
  }

  const getCurrentColor = () => {
    switch (dataKind) {
      case 'qoq': return COLORS.qoq
      case 'qoq_annualized': return COLORS.qoq_annualized
      case 'yoy': return COLORS.yoy
      default: return COLORS.qoq_annualized
    }
  }

  const getCompareIndicator = () => {
    switch (dataKind) {
      case 'qoq': return 'japan_gdp_qoq'
      case 'qoq_annualized': return 'japan_gdp_qoq_annualized'
      case 'yoy': return 'japan_gdp_yoy'
      default: return 'japan_gdp_qoq_annualized'
    }
  }

  return (
    <div id="japan-gdp-chart">
      <ChartContainer
        title="GDP成長率"
        showPeriodSelector={false}
        dataSource="内閣府"
        sourceUrl="https://www.esri.cao.go.jp/jp/sna/menu.html"
        handbookId="quarterly-gdp"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getCurrentLabel()}
          value={getCurrentLatest()?.value}
          valueColor={getCurrentColor()}
          date={getCurrentLatest()?.date}
          dateFormatter={formatQuarterLabel}
          nextRelease={nextRelease}
          format="percent"
          decimals={2}
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${getCompareIndicator()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {dataKind === 'qoq' && (
                    <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                  )}

                  {/* コンテンツ表示 */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && <QuarterlyTable data={qoqTableData} />}

                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <ZoomableChart
                        data={filteredQoQData}
                        dataKey="value"
                        color={COLORS.qoq}
                        name="GDP成長率（前期比）"
                        height={450}
                        tickFormatter={formatPercentage}
                        tooltipFormatter={formatPercentage}
                        tooltipLabelFormatter={(dateStr) => {
                          const date = new Date(dateStr)
                          const quarter = Math.floor(date.getMonth() / 3) + 1
                          return `${date.getFullYear()}年Q${quarter}`
                        }}
                        xAxisTickFormatter={(dateStr) => {
                          const date = new Date(dateStr)
                          const quarter = Math.floor(date.getMonth() / 3) + 1
                          return `${date.getFullYear()}/Q${quarter}`
                        }}
                        enableDynamicTicks={true}
                        showZeroLine={true}
                        showFiftyLine={false}
                        connectNulls={true}
                        hideLegend={true}
                      />
                    </>
                  )}

                  {dataKind === 'qoq_annualized' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <ZoomableChart
                        data={filteredQoQAnnualizedData}
                        dataKey="value"
                        color={COLORS.qoq_annualized}
                        name="GDP成長率（前期比年率）"
                        height={450}
                        tickFormatter={formatPercentage}
                        tooltipFormatter={formatPercentage}
                        tooltipLabelFormatter={(dateStr) => {
                          const date = new Date(dateStr)
                          const quarter = Math.floor(date.getMonth() / 3) + 1
                          return `${date.getFullYear()}年Q${quarter}`
                        }}
                        xAxisTickFormatter={(dateStr) => {
                          const date = new Date(dateStr)
                          const quarter = Math.floor(date.getMonth() / 3) + 1
                          return `${date.getFullYear()}/Q${quarter}`
                        }}
                        enableDynamicTicks={true}
                        showZeroLine={true}
                        showFiftyLine={false}
                        connectNulls={true}
                        hideLegend={true}
                      />
                    </>
                  )}

                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <ZoomableChart
                        data={filteredYoYData}
                        dataKey="value"
                        color={COLORS.yoy}
                        name="GDP成長率（前年比）"
                        height={450}
                        tickFormatter={formatPercentage}
                        tooltipFormatter={formatPercentage}
                        tooltipLabelFormatter={(dateStr) => {
                          const date = new Date(dateStr)
                          const quarter = Math.floor(date.getMonth() / 3) + 1
                          return `${date.getFullYear()}年Q${quarter}`
                        }}
                        xAxisTickFormatter={(dateStr) => {
                          const date = new Date(dateStr)
                          const quarter = Math.floor(date.getMonth() / 3) + 1
                          return `${date.getFullYear()}/Q${quarter}`
                        }}
                        enableDynamicTicks={true}
                        showZeroLine={true}
                        showFiftyLine={false}
                        connectNulls={true}
                        hideLegend={true}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="japan_gdp_qoq" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}

export default QuarterlyGDPChart
