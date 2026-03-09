/**
 * タームプレミアムチャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabelFull, type PeriodType } from '../common/useChartData'
import { NoDataMessage } from '../common/ChartComponents'
import { DARK_THEME } from '../common/chartConstants'

// Props型定義
interface TermPremiumItem {
  date: string
  yield_10y: number | null
  term_premium: number | null
  expected_rate: number | null
}

interface KWTermPremiumItem {
  date: string
  value: number
}

interface TermPremiumChartProps {
  data: TermPremiumItem[] | null
  kwData: KWTermPremiumItem[] | null
}

interface TermPremiumChartData {
  date: string
  value: number  // ZoomableChart requires this (mapped to acm_term_premium)
  yield_10y: number | null         // 10年債利回り (NY Fed ACM) → 右Y軸
  acm_term_premium: number | null  // ACMタームプレミアム (NY Fed) → 左Y軸
  kw_term_premium: number | null   // KWタームプレミアム (FRED) → 左Y軸
  expected_rate: number | null     // 期待短期金利 (NY Fed) → 右Y軸
  [key: string]: string | number | null | undefined
}

export default function TermPremiumChart({ data, kwData }: TermPremiumChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(2)

  // propsのデータをチャート用に変換・マージ
  const chartData = useMemo<TermPremiumChartData[]>(() => {
    if (!data || data.length === 0) return []

    // KWデータをMapに変換（日付でルックアップ用）
    const kwDataMap = new Map<string, number>()
    if (kwData) {
      kwData.forEach((item) => {
        kwDataMap.set(item.date, item.value)
      })
    }

    // ACMデータをベースにマージ
    const mergedData: TermPremiumChartData[] = data.map((item) => {
      const kwValue = kwDataMap.get(item.date) ?? null
      return {
        date: item.date,
        value: item.term_premium ?? 0,
        yield_10y: item.yield_10y,
        acm_term_premium: item.term_premium,
        kw_term_premium: kwValue,
        expected_rate: item.expected_rate,
      }
    })

    // 日付でソート（古い順）
    mergedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return mergedData
  }, [data, kwData])

  const formatPercentage = (value: number) => {
    if (value === null || value === undefined) return '-'
    return `${value.toFixed(2)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // X軸の表示間隔を動的に計算（データポイント数に基づく）
  const xAxisInterval = useMemo(() => {
    const dataLength = filteredData.length
    if (dataLength <= 30) return 0  // 30データポイント以下なら全て表示
    if (dataLength <= 60) return Math.floor(dataLength / 15)  // 約15ラベル表示
    if (dataLength <= 120) return Math.floor(dataLength / 12)  // 約12ラベル表示
    if (dataLength <= 365) return Math.floor(dataLength / 10)  // 約10ラベル表示
    return Math.floor(dataLength / 8)  // それ以上は約8ラベル表示
  }, [filteredData.length])

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="タームプレミアム" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="タームプレミアム" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 追加ライン設定（4ラインチャート）
  // ACM・KW タームプレミアム → 左Y軸、10年債利回り・期待短期金利 → 右Y軸
  const additionalLines = [
    {
      dataKey: 'kw_term_premium',
      color: '#fa8c16',  // オレンジ
      name: 'KWタームプレミアム',
    },
    {
      dataKey: 'yield_10y',
      color: '#1890ff',  // 青
      name: '10年債利回り',
      yAxisId: 'right',
    },
    {
      dataKey: 'expected_rate',
      color: '#52c41a',  // 緑
      name: '期待短期金利',
      yAxisId: 'right',
    },
  ]

  return (
    <div id="term-premium-chart">
      <ChartContainer
        title="タームプレミアム"
        showPeriodSelector={false}
        source="NY Fed, FRED"
        sourceUrl="https://www.newyorkfed.org/research/data_indicators/term-premia-tabs#/interactive"
      >
        {/* 期間セレクタ + 比較ボタン（横並び） */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=term_premium', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <ZoomableChart
          data={filteredData}
          dataKey="acm_term_premium"
          color="#722ed1"
          name="ACMタームプレミアム"
          height={450}
          tickFormatter={formatPercentage}
          xAxisTickFormatter={formatDateLabelFull}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={false}
          showDefaultTooltip={false}
          domain={['auto', 'auto']}
          additionalLines={additionalLines}
          initialHiddenLines={['kw_term_premium']}
          xAxisInterval={xAxisInterval}
          rightYAxis={{
            domain: ['auto', 'auto'],
            tickFormatter: formatPercentage,
          }}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
              return (
                <div
                  style={{
                    backgroundColor: DARK_THEME.bgTertiary,
                    border: `1px solid ${DARK_THEME.borderLight}`,
                    borderRadius: 8,
                    padding: '12px 16px',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                  }}
                >
                  <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
                    {formatDateLabelFull(String(label))}
                  </div>
                  {payload.map((item, index) => (
                    <div
                      key={index}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 4,
                        fontSize: 13,
                      }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            width: 10,
                            height: 10,
                            borderRadius: 2,
                            backgroundColor: item.color || '#1890ff',
                            marginRight: 6,
                          }}
                        />
                        {item.name}
                      </span>
                      <span style={{ fontWeight: 500, color: item.color || '#1890ff' }}>
                        {formatPercentage(item.value as number)}
                      </span>
                    </div>
                  ))}
                </div>
              )
            }}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
