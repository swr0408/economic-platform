/**
 * J.P.Morgan グローバル製造業PMIチャートコンポーネント
 *
 * データ:
 * - value: PMI指数値
 *
 * データソース:
 * - S&P Global / J.P.Morgan
 * - https://www.pmi.spglobal.com/Public/Release/PressReleases?language=en
 *
 * FMPマッピング: なし
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

import type { GlobalManufacturingPmiData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface GlobalManufacturingPmiChartProps {
  data: GlobalManufacturingPmiData | null
}

// カラー設定
const COLOR_PMI = '#1890ff'

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function GlobalManufacturingPmiChart({ data }: GlobalManufacturingPmiChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data ?? [])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="グローバル製造業PMI" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="グローバル製造業PMI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="global-manufacturing-pmi">
      <ChartContainer
        title="グローバル製造業PMI"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="S&P Global / J.P.Morgan"
        sourceUrl="https://www.pmi.spglobal.com/Public/Release/PressReleases?language=en"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="グローバル製造業PMI"
          value={latest?.value}
          valueColor={COLOR_PMI}
          date={latest?.date}
          decimals={1}
        />

        {/* データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=jpmorgan_global_manufacturing_pmi', '_blank')}
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
            { dataKey: 'value', color: COLOR_PMI, name: 'グローバル製造業PMI' },
          ]}
          yAxisFormatter={(v) => `${v}`}
          tooltipValueFormatter={(v) => v != null ? `${v.toFixed(1)}` : 'N/A'}
          yDomain={['dataMin - 1', 'dataMax + 1']}
          showZeroLine={false}
          showFiftyLine={true}
        />
      </ChartContainer>
    </div>
  )
}
