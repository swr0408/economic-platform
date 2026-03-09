/**
 * 台湾輸出受注（前年比）チャートコンポーネント
 *
 * データ:
 * - value: Export Orders YoY (%)
 *
 * データソース:
 * - MOEA (Ministry of Economic Affairs, Taiwan)
 * - DB: CSV過去データ + FMP蓄積データ
 *
 * FMPマッピング: taiwan_export_orders (TW / Export Orders YoY)
 *
 * 注意:
 * - 月初に速報値、月中旬に確報値が発表される
 * - 確報値で上書きされるため、常に最新の値が表示される
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { TaiwanExportOrdersData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface TaiwanExportOrdersChartProps {
  data: TaiwanExportOrdersData | null
}

type ActiveTab = 'timeseries' | 'market_impact'

const COLOR_EXPORT_ORDERS = '#2563EB'

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function TaiwanExportOrdersChart({ data }: TaiwanExportOrdersChartProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="台湾輸出受注（前年比）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="台湾輸出受注（前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="taiwan-export-orders">
      <ChartContainer
        title="台湾輸出受注（前年比）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="MOEA (Ministry of Economic Affairs, Taiwan)"
        sourceUrl="https://www.moea.gov.tw/MNS/dos/home/Home.aspx"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="台湾輸出受注（前年比）"
          value={latest?.value}
          valueColor={COLOR_EXPORT_ORDERS}
          date={latest?.date}
          decimals={1}
          unit="%"
          nextRelease={data.next_release ?? undefined}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as ActiveTab)}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=taiwan_export_orders', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* 線グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLOR_EXPORT_ORDERS, name: '台湾輸出受注（前年比）' },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => v != null ? `${v.toFixed(1)}%` : 'N/A'}
                    yDomain={['dataMin - 3', 'dataMax + 3']}
                    showZeroLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="taiwan_export_orders" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
