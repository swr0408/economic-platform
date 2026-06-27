/**
 * BOJ Tankan Unified Chart Component
 * 日銀短観 統合チャート（6種類のデータを左右ボタンで切り替え・長期時系列の折れ線）
 *
 * 1. 業況判断指数（DI） - 大企業製造業/非製造業の業況判断と先行き
 * 2. 設備投資額 - 大企業製造業/非製造業（前年度比）
 * 3. 生産・営業用設備判断指数（DI）
 * 4. 雇用人員判断指数（DI）
 * 5. 仕入価格判断指数（DI）
 * 6. 販売価格判断指数（DI）
 */

import { useEffect, useState, useMemo } from 'react'
import { Button } from 'antd'
import { LeftOutlined, RightOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  fetchBOJTankanData,
  type BOJTankanDataPoint,
  type NextRelease,
} from '../../../../utils/japan/bojTankanApi'

import { TEXT_COLORS } from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import {
  fetchBOJTankanComprehensiveTable,
  type DataType,
  type BOJTankanComprehensiveDataPoint,
} from '../../../../utils/japan/bojTankanComprehensiveApi'

type UnifiedDataType = 'business_conditions' | DataType

interface LineDef {
  dataKey: string
  name: string
  color: string
  hiddenByDefault?: boolean
}

interface DataTypeConfig {
  type: UnifiedDataType
  displayName: string
  unit: '%pt' | '%'
  lines: LineDef[]
}

const DI_4: LineDef[] = [
  { dataKey: 'all_industries_current', name: '大企業全産業 実績', color: '#0958d9' },
  { dataKey: 'all_industries_forecast', name: '大企業全産業 予測', color: '#91caff', hiddenByDefault: true },
  { dataKey: 'large_manufacturing_current', name: '大企業製造業 実績', color: '#cf1322' },
  { dataKey: 'large_manufacturing_forecast', name: '大企業製造業 予測', color: '#ffa39e', hiddenByDefault: true },
]

const DATA_TYPES: DataTypeConfig[] = [
  {
    type: 'business_conditions',
    displayName: '業況判断指数（DI）',
    unit: '%pt',
    lines: [
      { dataKey: 'large_manufacturing_current', name: '大企業製造業 業況判断', color: '#0958d9' },
      { dataKey: 'large_manufacturing_outlook', name: '大企業製造業 先行き', color: '#91caff', hiddenByDefault: true },
      { dataKey: 'large_non_manufacturing_current', name: '大企業非製造業 業況判断', color: '#cf1322' },
      { dataKey: 'large_non_manufacturing_outlook', name: '大企業非製造業 先行き', color: '#ffa39e', hiddenByDefault: true },
    ],
  },
  {
    type: 'capital_investment',
    displayName: '設備投資額（前年度比）',
    unit: '%',
    lines: [
      { dataKey: 'large_manufacturing', name: '大企業製造業', color: '#0958d9' },
      { dataKey: 'large_non_manufacturing', name: '大企業非製造業', color: '#cf1322' },
    ],
  },
  { type: 'production_facilities', displayName: '生産・営業用設備判断指数（DI）', unit: '%pt', lines: DI_4 },
  { type: 'employment', displayName: '雇用人員判断指数（DI）', unit: '%pt', lines: DI_4 },
  { type: 'purchase_price', displayName: '仕入価格判断指数（DI）', unit: '%pt', lines: DI_4 },
  { type: 'selling_price', displayName: '販売価格判断指数（DI）', unit: '%pt', lines: DI_4 },
]

// 次回発表日時のフォーマット
const formatNextRelease = (nextRelease: NextRelease | null | undefined): string | null => {
  if (!nextRelease) return null
  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`
  }
  if (nextRelease.time_jst && nextRelease.date) {
    const dt = new Date(nextRelease.date)
    return `${dt.getMonth() + 1}/${dt.getDate()} ${nextRelease.time_jst}`
  }
  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    return `${dt.getMonth() + 1}/${dt.getDate()}`
  }
  return null
}

const formatQuarterLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  const year = date.getFullYear() % 100
  const quarter = Math.floor(date.getMonth() / 3) + 1
  return `'${year.toString().padStart(2, '0')} Q${quarter}`
}

const formatFiscalLabel = (dateStr: string): string => {
  // 会計年度末(3/31)基準 → 年度ラベル（例: 2025-03-31 → FY24）
  const date = new Date(dateStr)
  const fy = (date.getMonth() <= 2 ? date.getFullYear() - 1 : date.getFullYear()) % 100
  return `FY${fy.toString().padStart(2, '0')}`
}

export default function BOJTankanUnifiedTable() {
  const [currentDataTypeIndex, setCurrentDataTypeIndex] = useState(0)
  const [diData, setDiData] = useState<BOJTankanDataPoint[]>([])
  const [comprehensiveData, setComprehensiveData] = useState<BOJTankanComprehensiveDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nextRelease, setNextRelease] = useState<NextRelease | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const currentDataType = DATA_TYPES[currentDataTypeIndex]
  const isCapital = currentDataType.type === 'capital_investment'

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)

        if (currentDataType.type === 'business_conditions') {
          const response = await fetchBOJTankanData()
          setDiData(response.data)
          setComprehensiveData([])
          if (response.next_release) setNextRelease(response.next_release)
        } else {
          const response = await fetchBOJTankanComprehensiveTable(currentDataType.type as DataType)
          setComprehensiveData(response.table_data)
          setDiData([])
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'データの取得に失敗しました')
        console.error('Error loading BOJ Tankan data:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [currentDataType.type])

  const handlePrevious = () => setCurrentDataTypeIndex((prev) => (prev - 1 + DATA_TYPES.length) % DATA_TYPES.length)
  const handleNext = () => setCurrentDataTypeIndex((prev) => (prev + 1) % DATA_TYPES.length)

  const chartData = useMemo(() => {
    const rawData = (currentDataType.type === 'business_conditions'
      ? diData
      : comprehensiveData) as unknown as Array<{ date: string } & Record<string, number | null>>
    return rawData.map((p) => ({ ...p }))
  }, [currentDataType.type, diData, comprehensiveData])

  const sortedData = useSortedData(chartData)
  const filteredData = usePeriodFiltering(sortedData, { selectedPeriod, defaultStartYear: 2018 })

  const yDomain = useMemo<[number, number]>(() => {
    const values = filteredData.flatMap((d) =>
      currentDataType.lines
        .map((l) => d[l.dataKey] as number | null)
        .filter((v): v is number => typeof v === 'number')
    )
    if (values.length === 0) return [-50, 50]
    const pad = isCapital ? 3 : 5
    const step = isCapital ? 2 : 5
    return [Math.floor((Math.min(...values) - pad) / step) * step, Math.ceil((Math.max(...values) + pad) / step) * step]
  }, [filteredData, currentDataType.lines, isCapital])

  const title = `日銀短観 ${currentDataType.displayName}`

  if (loading) return <LoadingChart title={title} />

  if (error) {
    return (
      <ChartContainer title={title} showPeriodSelector={false} showDataSource={false} handbookId="boj-tankan">
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  const lines = currentDataType.lines.map((l) => ({
    dataKey: l.dataKey,
    color: l.color,
    name: l.name,
    strokeWidth: l.hiddenByDefault ? 1.5 : 2.5,
    hide: hiddenSeries.has(l.dataKey),
  }))

  return (
    <div id="japan-boj-tankan-unified-table">
      <ChartContainer
        title={title}
        showPeriodSelector={false}
        dataSource="日本銀行"
        sourceUrl="https://www.boj.or.jp/statistics/tk/index.htm"
        handbookId="boj-tankan"
        extra={
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Button icon={<LeftOutlined />} onClick={handlePrevious} disabled={currentDataTypeIndex === 0} size="small" />
              <span style={{ fontSize: '12px', color: '#8c8c8c', minWidth: '40px', textAlign: 'center' }}>
                {currentDataTypeIndex + 1}/{DATA_TYPES.length}
              </span>
              <Button
                icon={<RightOutlined />}
                onClick={handleNext}
                disabled={currentDataTypeIndex === DATA_TYPES.length - 1}
                size="small"
              />
            </div>
            {nextRelease && formatNextRelease(nextRelease) && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: TEXT_COLORS.secondary }}>
                <CalendarOutlined />
                <span>次回発表: {formatNextRelease(nextRelease)}</span>
              </div>
            )}
          </div>
        }
      >
        <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        </div>

        {filteredData.length === 0 ? (
          <NoDataMessage />
        ) : (
          <StandardLineChart
            data={filteredData}
            lines={lines}
            yAxisFormatter={(v) => `${v.toFixed(0)}`}
            yDomain={yDomain}
            showZeroLine={true}
            xAxisFormatter={isCapital ? formatFiscalLabel : formatQuarterLabel}
            tooltipLabelFormatter={isCapital ? formatFiscalLabel : formatQuarterLabel}
            tooltipValueFormatter={(v) => `${v.toFixed(1)} ${currentDataType.unit}`}
            onLegendClick={handleLegendClick}
          />
        )}
      </ChartContainer>
    </div>
  )
}
