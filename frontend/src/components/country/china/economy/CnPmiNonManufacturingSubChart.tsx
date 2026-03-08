/**
 * 中国 非製造業PMIサブインデックスチャート
 *
 * 9系列: サービス業、建設業、新規受注、輸出新規受注、手持ち受注、
 *        販売価格、投入価格、サプライヤー納期、雇用
 * 折れ線グラフ（50ラインをゼロ線として表示）
 *
 * データソース: NBS（国家統計局）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type {
  CnPmiData,
  CnPmiNmfSubItem,
} from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnPmiData | null
}

interface ChartDataPoint {
  date: string
  services: number | null
  construction: number | null
  new_orders: number | null
  export_new_orders: number | null
  in_hand_orders: number | null
  sale_price: number | null
  input_price: number | null
  supplier_delivery: number | null
  employment: number | null
}

const SERIES_CONFIG = [
  { dataKey: 'services', color: '#1890ff', name: 'サービス業' },
  { dataKey: 'construction', color: '#52c41a', name: '建設業' },
  { dataKey: 'new_orders', color: '#fa541c', name: '新規受注' },
  { dataKey: 'export_new_orders', color: '#722ed1', name: '輸出新規受注' },
  { dataKey: 'in_hand_orders', color: '#eb2f96', name: '手持ち受注' },
  { dataKey: 'sale_price', color: '#faad14', name: '販売価格' },
  { dataKey: 'input_price', color: '#13c2c2', name: '投入価格' },
  { dataKey: 'supplier_delivery', color: '#8c8c8c', name: 'サプライヤー納期' },
  { dataKey: 'employment', color: '#cf1322', name: '雇用' },
]

// 初期表示で非表示にするサブ指標
const INITIAL_HIDDEN = new Set(['in_hand_orders', 'sale_price', 'input_price', 'supplier_delivery', 'export_new_orders'])

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

export default function CnPmiNonManufacturingSubChart({ data }: Props) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(5)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(INITIAL_HIDDEN)

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.non_manufacturing_sub?.data) return []
    return data.non_manufacturing_sub.data.map((d: CnPmiNmfSubItem) => ({
      date: d.date,
      services: d.services,
      construction: d.construction,
      new_orders: d.new_orders,
      export_new_orders: d.export_new_orders,
      in_hand_orders: d.in_hand_orders,
      sale_price: d.sale_price,
      input_price: d.input_price,
      supplier_delivery: d.supplier_delivery,
      employment: d.employment,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  if (!data?.non_manufacturing_sub) {
    return (
      <div id="non-manufacturing-pmi-sub">
        <ChartContainer title="非製造業PMIサブインデックス">
          <LoadingChart title="非製造業PMIサブインデックス" />
        </ChartContainer>
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div id="non-manufacturing-pmi-sub">
        <ChartContainer title="非製造業PMIサブインデックス">
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = data.non_manufacturing_sub.latest

  return (
    <div id="non-manufacturing-pmi-sub">
      <ChartContainer
        title="非製造業PMIサブインデックス"
        showDataSource={true}
        dataSource="NBS"
        sourceUrl="https://www.stats.gov.cn/english/PressRelease/"
      >
        {/* 最新値ボックス */}
        <div style={{ ...LATEST_VALUE_BOX_STYLE, flexWrap: 'wrap' }}>
          {latest?.date && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, marginRight: 12 }}>
              {formatDateFull(latest.date)}
            </span>
          )}
          {SERIES_CONFIG.map(s => (
            <_LatestBox
              key={s.dataKey}
              label={s.name}
              value={latest?.[s.dataKey as keyof CnPmiNmfSubItem] as number | null | undefined}
              color={s.color}
              hidden={hiddenSeries.has(s.dataKey)}
              onClick={() => handleLegendClick(s.dataKey)}
            />
          ))}
        </div>

        {/* データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=cn_pmi_non_manufacturing', '_blank')}
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
          lines={SERIES_CONFIG.map(s => ({
            dataKey: s.dataKey,
            color: s.color,
            name: s.name,
            hide: hiddenSeries.has(s.dataKey),
          }))}
          xAxisFormatter={formatDateLabel}
          yAxisFormatter={(v: number) => `${v}`}
          yDomain={['dataMin - 1', 'dataMax + 1']}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v: number) => `${v.toFixed(1)}`}
          showFiftyLine={true}
          showZeroLine={false}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}

function _LatestBox({
  label,
  value,
  color,
  hidden,
  onClick,
}: {
  label: string
  value: number | null | undefined
  color: string
  hidden: boolean
  onClick: () => void
}) {
  return (
    <span
      onClick={onClick}
      style={{
        cursor: 'pointer',
        opacity: hidden ? 0.3 : 1,
        marginRight: 12,
        marginBottom: 4,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 3,
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: color,
        }}
      />
      <span style={{ fontSize: 11, color: '#666' }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 700, color }}>
        {value != null ? value.toFixed(1) : '—'}
      </span>
    </span>
  )
}
