/**
 * ECB CISS（システミックストレス総合指標）チャートコンポーネント
 *
 * ユーロ圏のシステミックストレスを測定する総合指標
 * 値は0〜1の範囲で、高いほどストレスが大きい
 *
 * データソース:
 * - European Central Bank
 * - CISS.D.U2.Z0Z.4F.EC.SS_CIN.IDX
 *
 * 発表スケジュール:
 * - 日次（営業日ベース、15:00 CET）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox, StandardLineChart } from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { ECBCISSData } from '../../../../hooks/useDashboardData'

interface CISSChartProps {
  data: ECBCISSData | null
}

export default function CISSChart({ data }: CISSChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)

  // データをチャート用に変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return data.data
      .filter((item) => item.value !== null && item.value !== undefined)
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="システミックストレス指標（CISS）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="システミックストレス指標（CISS）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-ciss-chart">
      <ChartContainer
        title="システミックストレス指標（CISS）"
        showPeriodSelector={false}
        dataSource="European Central Bank"
        sourceUrl="https://data.ecb.europa.eu/data/datasets/CISS"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="CISS"
          value={latestValue?.value}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="number"
          decimals={4}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ecb_ciss', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: CHART_COLORS.primary, name: 'CISS' },
          ]}
          yAxisFormatter={(v) => v.toFixed(2)}
          tooltipValueFormatter={(v) => v.toFixed(4)}
          yDomain={[0, 'dataMax + 0.1']}
        />
      </ChartContainer>
    </div>
  )
}
