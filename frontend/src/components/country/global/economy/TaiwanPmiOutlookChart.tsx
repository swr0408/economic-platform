/**
 * 台湾PMI先行き（電子工学業）チャートコンポーネント
 *
 * データ:
 * - value: Future Outlooks index (Electronic & Optical industry)
 *
 * データソース:
 * - CIER (Chung-Hua Institution for Economic Research)
 *
 * FMPマッピング: なし（S&P Global PMIとは別のサーベイ）
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
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

import type { TaiwanPmiOutlookData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface TaiwanPmiOutlookChartProps {
  data: TaiwanPmiOutlookData | null
}

const COLOR_OUTLOOK = '#722ed1'

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function TaiwanPmiOutlookChart({ data }: TaiwanPmiOutlookChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2012,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="台湾PMI先行き（電子工学業）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="台湾PMI先行き（電子工学業）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="taiwan-pmi-outlook">
      <ChartContainer
        title="台湾PMI先行き（電子工学業）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="CIER (Chung-Hua Institution for Economic Research)"
        sourceUrl="https://www.cier.edu.tw/en/eco_cat/pmi-en/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="台湾PMI先行き"
          value={latest?.value}
          valueColor={COLOR_OUTLOOK}
          date={latest?.date}
          decimals={1}
        />

        {/* データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=taiwan_pmi_outlook', '_blank')}
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
            { dataKey: 'value', color: COLOR_OUTLOOK, name: '台湾PMI先行き' },
          ]}
          yAxisFormatter={(v) => `${v}`}
          tooltipValueFormatter={(v) => v != null ? `${v.toFixed(1)}` : 'N/A'}
          yDomain={['dataMin - 2', 'dataMax + 2']}
          showZeroLine={false}
          showFiftyLine={true}
        />
      </ChartContainer>
    </div>
  )
}
