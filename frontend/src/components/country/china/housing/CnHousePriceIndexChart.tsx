/**
 * 中国 住宅価格指数（House Price Index YoY）チャートコンポーネント
 *
 * 70都市新築商品住宅価格指数の前年比を折れ線グラフで表示
 *
 * データソース: NBS / FMP
 *
 * FMPマッピング: cn_house_price_index → "House Price Index YoY"
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { CnHousePriceIndexData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnHousePriceIndexData | null
}

const COLOR_PRIMARY = '#DC143C'  // クリムゾン

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnHousePriceIndexChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState('timeseries')
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('raw', { raw: 10 })

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="住宅価格指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="住宅価格指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="house-price-index">
      <ChartContainer
        title="住宅価格指数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="NBS"
        sourceUrl="https://www.stats.gov.cn/english/PressRelease/index.html"
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          size="small"
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 最新値表示 */}
                  <SimpleLatestValueBox
                    label="住宅価格指数（YoY）"
                    value={latest?.value ?? null}
                    date={latest?.date}
                    unit="%"
                    decimals={1}
                    valueColor={COLOR_PRIMARY}
                    dateFormatter={formatDateFull}
                    nextRelease={data.next_release ?? null}
                  />

                  {/* データ比較ボタン（右寄せ） */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_house_price_index', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間選択 */}
                  <PeriodSelector
                    onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
                    selectedPeriod={currentPeriod}
                  />

                  {/* グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLOR_PRIMARY, name: '住宅価格指数（YoY）' },
                    ]}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    yDomain={['dataMin - 2', 'dataMax + 2']}
                    xAxisFormatter={formatDateLabel}
                    tooltipLabelFormatter={formatDateFull}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                    showZeroLine={true}
                    showLegend={false}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cn_house_price_index" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
