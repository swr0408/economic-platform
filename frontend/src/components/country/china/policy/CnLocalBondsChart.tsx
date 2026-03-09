/**
 * 中国 地方政府債券チャートコンポーネント
 *
 * ボタン切替で4系列を個別表示:
 * - 新規比率 (new_ratio): 当月新増合計 / 当月総発行額 × 100 (%)
 * - 新規専項比率 (special_ratio): 当月新増専項 / 当月新増合計 × 100 (%)
 * - 枠余地 (headroom): 債務限額合計 − 債務残高合計 (億元)
 * - コスト (cost): (当月平均発行利率 + 年初来平均発行利率) / 2 (%)
 *
 * データソース: 中国財政部 (yss.mof.gov.cn)
 *
 * FMPマッピング: なし
 */
import { useState, useMemo } from 'react'
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
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'

import type { CnLocalBondsData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnLocalBondsData | null
}

interface ChartDataPoint {
  date: string
  new_ratio: number | null
  special_ratio: number | null
  headroom: number | null
  cost: number | null
}

type DataKind = 'new_ratio' | 'special_ratio' | 'headroom' | 'cost'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'new_ratio', label: '新規比率' },
  { mode: 'special_ratio', label: '専項比率' },
  { mode: 'headroom', label: '枠余地' },
  { mode: 'cost', label: 'コスト' },
]

const COLORS: Record<DataKind, string> = {
  new_ratio: '#1890ff',
  special_ratio: '#52c41a',
  headroom: '#fa8c16',
  cost: '#DC143C',
}

const LABELS: Record<DataKind, string> = {
  new_ratio: '新規比率',
  special_ratio: '新規専項比率',
  headroom: '枠余地',
  cost: '発行コスト',
}

const UNITS: Record<DataKind, string> = {
  new_ratio: '%',
  special_ratio: '%',
  headroom: '億元',
  cost: '%',
}

const COMPARE_IDS: Record<DataKind, string> = {
  new_ratio: 'cn_local_bonds_new_ratio',
  special_ratio: 'cn_local_bonds_special_ratio',
  headroom: 'cn_local_bonds_headroom',
  cost: 'cn_local_bonds_cost',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnLocalBondsChart({ data }: Props) {
  const [dataKind, setDataKind] = useState<DataKind>('new_ratio')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.data) return []
    return data.data.map(d => ({
      date: d.date,
      new_ratio: d.new_ratio,
      special_ratio: d.special_ratio,
      headroom: d.headroom,
      cost: d.cost,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2021,
  })

  if (data === null) {
    return (
      <div id="cn-local-bonds">
        <LoadingChart title="地方債" />
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div id="cn-local-bonds">
        <ChartContainer title="地方債" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = data.latest
  const currentValue = latest ? latest[dataKind] : null
  const isPercent = dataKind !== 'headroom'

  return (
    <div id="cn-local-bonds">
      <ChartContainer
        title="地方債"
        showPeriodSelector={false}
        dataSource="中国財政部"
        sourceUrl="https://yss.mof.gov.cn/zhuantilanmu/dfzgl/sjtj/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={LABELS[dataKind]}
          value={currentValue}
          valueColor={COLORS[dataKind]}
          date={latest?.date}
          format={isPercent ? 'percent' : 'number'}
          unit={UNITS[dataKind]}
        />

        {/* 上段: 指標種別 + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <ViewModeButtonGroup
            options={DATA_KIND_OPTIONS}
            currentMode={dataKind}
            onChange={setDataKind}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open(`/compare?s=${COMPARE_IDS[dataKind]}`, '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間セレクター */}
        <PeriodSelector
          onPeriodChange={setCurrentPeriod}
          selectedPeriod={currentPeriod}
        />

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: dataKind, color: COLORS[dataKind], name: LABELS[dataKind] },
          ]}
          yAxisFormatter={isPercent
            ? (v: number) => `${v}%`
            : (v: number) => `${(v / 10000).toFixed(1)}万`
          }
          yDomain={isPercent ? ['dataMin - 5', 'dataMax + 5'] : ['dataMin - 5000', 'dataMax + 5000']}
          tooltipValueFormatter={(v: number) =>
            isPercent ? `${v.toFixed(2)}%` : `${v.toLocaleString()} 億元`
          }
          showZeroLine={false}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
