/**
 * 中国預金準備率（Reserve Requirement Ratio）チャートコンポーネント
 *
 * データ:
 * - Large Bank の月末預金準備率 (%)
 *
 * データソース:
 * - 中国人民銀行（PBOC）武漢支行
 * - https://wuhan.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html
 *
 * 更新: 毎営業日 JST 16:00 自動取得
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
  SimpleLatestValueBox,
} from '../../usa/common/ChartComponents'

import type { ChRrrData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface ChRrrChartProps {
  data: ChRrrData | null
}

const COLOR_RRR = '#ef4444'  // レッド

// =============================================================================
// 日付フォーマット
// =============================================================================

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

export default function ChRrrChart({ data }: ChRrrChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="預金準備率（大型金融機関）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="預金準備率（大型金融機関）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="rrr">
      <ChartContainer
        title="預金準備率（大型金融機関）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国人民銀行"
        sourceUrl="https://wuhan.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html"
      >
        {/* 最新値 */}
        <SimpleLatestValueBox
          value={latest?.value ?? null}
          date={latest?.date}
          label="預金準備率（大型行）"
          unit="%"
          valueColor={COLOR_RRR}
          decimals={2}
          dateFormatter={formatDateFull}
        />

        {/* 期間選択 + データ比較ボタン */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 8,
        }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=china_reserve_requirement_ratio_for_large_banks', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 折れ線グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLOR_RRR, name: '預金準備率 (%)' },
          ]}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
          showZeroLine={false}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
