/**
 * UK Public Sector Net Borrowing Ex Banks チャートコンポーネント
 *
 * イギリスの公的部門純借入（銀行除く）データを表示
 *
 * 指標:
 * - PSNB Ex: 公的部門純借入（銀行除く）
 * - CGNB: 中央政府純借入
 * - PSND Ex: 公的部門純債務（銀行除く）
 * - PSND/GDP: 公的部門純債務対GDP比
 *
 * データソース:
 * - Office for National Statistics (ONS)
 *
 * 発表スケジュール:
 * - 月次（通常、翌月下旬）
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox, DataTypeButtonGroup } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { UKPublicSectorNetBorrowingData } from '../../../../hooks/useDashboardData'

interface UKPublicSectorNetBorrowingChartProps {
  data: UKPublicSectorNetBorrowingData | null
}

// データ種別
type DataType = 'psnb_ex' | 'cgnb' | 'psnd_ex' | 'psnd_gdp'

const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'psnb_ex', label: '公的部門純債務（公的部門銀行除く）GDP比：NSA' },
  { type: 'cgnb', label: '公的部門純債務（公的部門銀行およびイングランド銀行除く）GDP比：NSA' },
  { type: 'psnd_ex', label: '公的部門純借入（公的部門銀行除く）' },
  { type: 'psnd_gdp', label: '公的部門純債務（公的部門銀行除く）' },
]

// 色定義
const COLORS = {
  psnb_ex: '#ef4444',
  cgnb: '#3b82f6',
  psnd_ex: '#22c55e',
  psnd_gdp: '#f59e0b',
}

export default function UKPublicSectorNetBorrowingChart({ data }: UKPublicSectorNetBorrowingChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataType, setDataType] = useState<DataType>('psnb_ex')

  // propsのデータをチャート用に変換
  const chartData = useMemo(() => {
    if (!data) return []

    const sourceData = data[dataType] || []
    if (sourceData.length === 0) return []

    const formattedData = sourceData.map((item: any) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a: any, b: any) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data, dataType])

  // 単位フォーマット（ツールチップ/詳細表示用：高精度）
  const formatValue = (value: number) => {
    // PSNB Ex, CGNB: パーセント表示
    if (dataType === 'psnb_ex' || dataType === 'cgnb') {
      return `${value.toFixed(2)}%`
    }
    // PSND Ex, PSND/GDP: £ million → £ billion変換
    const billion = value / 1000
    return `£${billion.toFixed(2)}B`
  }

  // Y軸ティック用フォーマット（コンパクト：軸幅でのクリップを防ぐ）
  const formatAxisValue = (value: number) => {
    // パーセント系は小数なし
    if (dataType === 'psnb_ex' || dataType === 'cgnb') {
      return `${Math.round(value)}%`
    }
    // £ million → 兆(T)/十億(B) のコンパクト表記
    const billion = value / 1000
    if (Math.abs(billion) >= 1000) {
      return `£${(billion / 1000).toFixed(1)}T`
    }
    return `£${Math.round(billion)}B`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const getLatestValue = () => {
    switch (dataType) {
      case 'psnb_ex':
        return data?.latest_psnb_ex
      case 'cgnb':
        return data?.latest_cgnb
      case 'psnd_ex':
        return data?.latest_psnd_ex
      case 'psnd_gdp':
        return data?.latest_psnd_gdp
      default:
        return null
    }
  }

  const latestValue = getLatestValue()

  // データラベル取得
  const getDataLabel = () => {
    switch (dataType) {
      case 'psnb_ex':
        return '公的部門純債務（公的部門銀行除く）GDP比：NSA'
      case 'cgnb':
        return '公的部門純債務（公的部門銀行およびイングランド銀行除く）GDP比：NSA'
      case 'psnd_ex':
        return '公的部門純借入（公的部門銀行を除く）'
      case 'psnd_gdp':
        return '公的部門純債務（公的部門銀行除く）'
      default:
        return ''
    }
  }

  // 比較ページ用ID取得
  const getCompareIds = () => {
    switch (dataType) {
      case 'psnb_ex':
        return 'uk_psnb_ex'
      case 'cgnb':
        return 'uk_cgnb'
      case 'psnd_ex':
        return 'uk_psnd_ex'
      case 'psnd_gdp':
        return 'uk_psnd_gdp'
      default:
        return 'uk_psnb_ex'
    }
  }

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="公的部門純借入（イギリス）" />
  }

  return (
    <div id="uk-public-sector-net-borrowing-chart">
      <ChartContainer
        title="公的部門純借入"
        showPeriodSelector={false}
        dataSource="Office for National Statistics"
        sourceUrl="https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicsectorfinance?utm_source=chatgpt.com"
        handbookId="uk-public-sector-net-borrowing"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getDataLabel()}
          value={
            // PSND Ex, PSND/GDP: million → billion変換
            (dataType === 'psnd_ex' || dataType === 'psnd_gdp') && latestValue?.value
              ? latestValue.value / 1000
              : latestValue?.value
          }
          valueColor={COLORS[dataType]}
          date={latestValue?.date}
          nextRelease={
            data.next_release
              ? {
                  date: data.next_release.date,
                  label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined,
                }
              : null
          }
          format={(dataType === 'psnb_ex' || dataType === 'cgnb') ? 'percent' : 'number'}
          decimals={2}
          unit={(dataType === 'psnb_ex' || dataType === 'cgnb') ? '%' : '£B'}
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* データ種別切り替え */}
                  <DataTypeButtonGroup
                    options={DATA_TYPE_OPTIONS}
                    currentType={dataType}
                    onChange={setDataType}
                  />

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${getCompareIds()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {hasData ? (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="value"
                      color={COLORS[dataType]}
                      name={getDataLabel()}
                      height={450}
                      tickFormatter={formatAxisValue}
                      xAxisTickFormatter={formatDateLabel}
                      enableDynamicTicks={true}
                      showZeroLine={true}
                      showFiftyLine={false}
                      connectNulls={true}
                      hideLegend={true}
                      showDefaultTooltip={false}
                      domain={['dataMin - 5', 'dataMax + 5']}
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
                                {formatDateLabel(String(label))}
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
                                        backgroundColor: item.color || COLORS[dataType],
                                        marginRight: 6,
                                      }}
                                    />
                                    {item.name}
                                  </span>
                                  <span style={{ fontWeight: 500, color: item.color || COLORS[dataType] }}>
                                    {formatValue(item.value as number)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )
                        }}
                      />
                    </ZoomableChart>
                  ) : (
                    <NoDataMessage />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="uk_public_sector_net_borrowing_ex_bank" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
