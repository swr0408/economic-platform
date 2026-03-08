/**
 * 中国人民銀行バランスシート（総資産）チャートコンポーネント
 *
 * データ:
 * - 総資産（Total Assets of Monetary Authority）: 月末値、単位: 億元
 *
 * データソース:
 * - 中国人民銀行
 * - https://camlmac.pbc.gov.cn/diaochatongjisi/116219/116319/index.html
 *
 * 更新: 毎月月次データ公表後に自動取得
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

import type { ChCbsData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface ChCentralBankBalanceSheetChartProps {
  data: ChCbsData | null
}

const COLOR_CBS = '#8b5cf6'  // パープル

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

export default function ChCentralBankBalanceSheetChart({ data }: ChCentralBankBalanceSheetChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="中銀バランスシート（総資産）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="中銀バランスシート（総資産）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]
  // 億元 → 兆元に換算して表示（視認性向上）
  const latestTrillion = latest?.value != null ? latest.value / 10000 : null

  return (
    <div id="central-bank-balance-sheet">
      <ChartContainer
        title="中銀バランスシート（総資産）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国人民銀行"
        sourceUrl="https://camlmac.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"
      >
        {/* 最新値: 兆元表示 */}
        <SimpleLatestValueBox
          value={latestTrillion}
          date={latest?.date}
          label="総資産"
          unit="兆元"
          valueColor={COLOR_CBS}
          decimals={2}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ?? null}
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
              onClick={() => window.open('/compare?s=ch_central_bank_balance_sheet', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 折れ線グラフ（億元で描画） */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLOR_CBS, name: '総資産 (億元)' },
          ]}
          yAxisFormatter={(v) => `${(v / 10000).toFixed(0)}兆`}
          yDomain={['dataMin - 5000', 'dataMax + 5000']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v) => `${(v / 10000).toFixed(2)} 兆元`}
          showZeroLine={false}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
