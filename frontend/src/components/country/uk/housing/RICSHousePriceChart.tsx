/**
 * RICS住宅価格バランスチャートコンポーネント
 *
 * データ:
 * - RICS House Price Balance（住宅価格の上昇・下落を示すサーベイ指標）
 *
 * 表示モード:
 * - 折れ線グラフ: 時系列データ
 * - 予測タブ: RICSレポートPDFの予測チャート（6ページ目）
 *
 * データソース:
 * - DB: economic_calendar_events（FMP蓄積データ）
 * - PDF: RICS UK Residential Market Survey
 *
 * 発表スケジュール:
 * - 月次（不定期・FMPカレンダーから取得）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip, Tabs, Spin, Alert, Modal, Typography } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import {
  fetchRICSSurvey,
  getRICSSurveyImageUrl,
  type RICSSurveyData,
} from '../../../../utils/uk/ricsSurveyApi'

const { Link, Text } = Typography

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatDateLabel,
  formatDateLabelJP,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { RICSHousePriceData } from '../../../../hooks/useDashboardData'

interface RICSHousePriceChartProps {
  data: RICSHousePriceData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

type ViewMode = 'chart'

// ビューモード設定（単一なので空）
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = []

// グラフの色
const COLORS = {
  value: '#3498db', // メイン - 青
}

// 系列名
const SERIES_NAMES = {
  value: 'RICS住宅価格',
}

export default function RICSHousePriceChart({ data }: RICSHousePriceChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('chart')

  // RICS Survey forecast data
  const [surveyData, setSurveyData] = useState<RICSSurveyData | null>(null)
  const [surveyLoading, setSurveyLoading] = useState(false)
  const [surveyError, setSurveyError] = useState<string | null>(null)
  const [modalVisible, setModalVisible] = useState(false)

  // Fetch RICS survey data when forecast tab is clicked
  const loadSurveyData = () => {
    if (surveyData || surveyLoading) return

    setSurveyLoading(true)
    fetchRICSSurvey()
      .then((result) => {
        setSurveyData(result)
        setSurveyError(null)
      })
      .catch((err) => {
        setSurveyError('RICS調査データの取得に失敗しました')
        console.error('Error fetching RICS survey:', err)
      })
      .finally(() => {
        setSurveyLoading(false)
      })
  }

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    chart: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map(point => ({
      date: point.date,
      value: point.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (chartData.length === 0) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  const nextRelease = data?.next_release

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="RICS住宅価格バランス" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="RICS住宅価格バランス" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest || latest.value === null) return []

    return [
      {
        label: 'バランス',
        value: `${latest.value >= 0 ? '+' : ''}${latest.value.toFixed(0)}`,
        color: latest.value >= 0 ? '#f5222d' : '#52c41a',
      },
    ]
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_rics_house_price', '_blank')
  }

  return (
    <div id="uk-rics-house-price-chart">
      <ChartContainer
        title="RICS住宅価格バランス"
        showPeriodSelector={false}
        dataSource="RICS"
        sourceUrl="https://www.rics.org/news-insights/market-surveys/uk-residential-market-survey"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        <Tabs
          defaultActiveKey="chart"
          onChange={(key) => {
            if (key === 'forecast') {
              loadSurveyData()
            }
          }}
          items={[
            {
              key: 'chart',
              label: '時系列',
              children: (
                <>
                  {/* ビューモード切り替え */}
                  <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

                  {/* 折れ線グラフ */}
                  {viewMode === 'chart' && (
                    <>
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
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          {
                            dataKey: 'value',
                            color: COLORS.value,
                            name: SERIES_NAMES.value,
                          },
                        ]}
                        xAxisFormatter={formatDateLabel}
                        yAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                        tooltipLabelFormatter={formatDateLabelJP}
                        yDomain={['dataMin - 5', 'dataMax + 5']}
                        showZeroLine
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'forecast',
              label: '予測',
              children: (
                <div style={{ padding: '16px 0' }}>
                  {surveyLoading ? (
                    <div style={{ textAlign: 'center', padding: '50px 0' }}>
                      <Spin size="large" />
                    </div>
                  ) : surveyError ? (
                    <Alert
                      message="データ取得エラー"
                      description={surveyError}
                      type="error"
                      showIcon
                    />
                  ) : surveyData?.forecast_image ? (
                    <>
                      <div style={{ marginBottom: 16, textAlign: 'center' }}>
                        <Text type="secondary">
                          レポート日: {surveyData.report_date || '不明'}
                        </Text>
                        {surveyData.pdf_url && (
                          <>
                            {' | '}
                            <Link href={surveyData.pdf_url} target="_blank" rel="noopener noreferrer">
                              PDF全文を見る
                            </Link>
                          </>
                        )}
                      </div>
                      <img
                        src={getRICSSurveyImageUrl(surveyData.forecast_image)}
                        alt="RICS Survey Forecast"
                        style={{ width: '40%', height: 'Auto', cursor: 'pointer', display: 'block', margin: '0 auto'}}
                        onClick={() => setModalVisible(true)}
                      />
                      <Modal
                        open={modalVisible}
                        title="RICS住宅市場調査 - 予測チャート"
                        onCancel={() => setModalVisible(false)}
                        footer={null}
                        width="50%"
                        style={{ top: 20 }}
                        styles={{ body: { padding: '10px' } }}
                      >
                        <img
                          src={getRICSSurveyImageUrl(surveyData.forecast_image)}
                          alt="RICS Survey Forecast"
                          style={{ width: '100%', height: 'auto' }}
                        />
                      </Modal>
                    </>
                  ) : (
                    <Alert
                      message="データなし"
                      description="予測チャートが見つかりませんでした"
                      type="warning"
                      showIcon
                    />
                  )}
                </div>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="rics_house_price" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
