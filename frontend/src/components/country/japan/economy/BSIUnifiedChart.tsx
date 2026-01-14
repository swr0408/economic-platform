/**
 * BSI Unified Chart Component
 * 法人企業景気予測調査 統合チャート
 * Displays all 4 BSI sheets with navigation buttons to switch between them
 * Each sheet shows period types switchable by tabs: actual, forecast1, forecast2
 */

import { useState, useEffect, useMemo } from 'react'
import { Button, Segmented } from 'antd'
import { LeftOutlined, RightOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import { type PeriodValue } from '../../../common/PeriodSelector'
import { fetchBSIComprehensiveChart, type SheetName, type PeriodType, type NextRelease } from '../../../../utils/japan/bsiApi'
import { TEXT_COLORS } from '../../usa/common/chartConstants'

interface SheetConfig {
  sheetName: SheetName
  displayName: string
}

interface ChartDataPoint {
  date: string
  value: number
  large_all_industries: number | null
  large_manufacturing: number | null
  large_non_manufacturing: number | null
  medium_all_industries: number | null
  small_all_industries: number | null
  [key: string]: unknown
}

const SHEETS: SheetConfig[] = [
  { sheetName: 'ref1', displayName: '貴社の景況' },
  { sheetName: 'ref2', displayName: '国内の景況' },
  { sheetName: 'ref3', displayName: '設備投資' },
  { sheetName: 'ref4', displayName: '雇用' },
]

const PERIOD_TYPES: { type: PeriodType; label: string }[] = [
  { type: 'actual', label: '当期' },
  { type: 'forecast1', label: '翌期予測' },
  { type: 'forecast2', label: '翌々期予測' },
]

const DEFAULT_START_DATE = '2010-Q1'

// 次回発表日時のフォーマット
const formatNextRelease = (nextRelease: NextRelease | null | undefined): string | null => {
  if (!nextRelease) return null
  if (nextRelease.datetime_jst) {
    const dt = new Date(nextRelease.datetime_jst)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    const hours = dt.getHours().toString().padStart(2, '0')
    const minutes = dt.getMinutes().toString().padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  }
  if (nextRelease.time_jst && nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day} ${nextRelease.time_jst}`
  }
  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    return `${month}/${day}`
  }
  return null
}

const parseQuarterDate = (dateStr: string): Date | null => {
  try {
    return new Date(dateStr)
  } catch {
    return null
  }
}

const formatQuarterLabel = (dateStr: string): string => {
  try {
    const date = new Date(dateStr)
    const year = date.getFullYear() % 100
    const month = date.getMonth() + 1
    const quarter = Math.ceil(month / 3)
    return `'${year.toString().padStart(2, '0')} Q${quarter}`
  } catch {
    return dateStr
  }
}

const filterByPeriod = <T extends { date: string }>(data: T[], period: PeriodValue, defaultStart = DEFAULT_START_DATE) => {
  if (period === 'all') return data

  const cutoff =
    period === 'default'
      ? (() => {
          const match = defaultStart.match(/^(\d{4})-Q(\d)$/)
          if (match) {
            const year = parseInt(match[1])
            const quarter = parseInt(match[2])
            const month = (quarter - 1) * 3
            return new Date(year, month, 1)
          }
          return new Date(defaultStart)
        })()
      : (() => {
          const years = typeof period === 'number' ? period : 0
          const d = new Date()
          d.setFullYear(d.getFullYear() - years)
          return d
        })()

  if (!cutoff) return data
  return data.filter(({ date }) => {
    const parsed = parseQuarterDate(date)
    return parsed && parsed >= cutoff
  })
}

export default function BSIUnifiedChart() {
  const [currentSheetIndex, setCurrentSheetIndex] = useState(0)
  const [selectedPeriodType, setSelectedPeriodType] = useState<PeriodType>('actual')
  const [rawData, setRawData] = useState<ChartDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>('default')
  const [nextRelease, setNextRelease] = useState<NextRelease | null>(null)

  const currentSheet = SHEETS[currentSheetIndex]
  const currentPeriodLabel = PERIOD_TYPES.find((p) => p.type === selectedPeriodType)?.label || '当期'

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetchBSIComprehensiveChart(currentSheet.sheetName, selectedPeriodType)

        const chartData: ChartDataPoint[] = response.chart_data.dates.map((date, index) => ({
          date,
          value: response.chart_data.large_all_industries[index] ?? 0,
          large_all_industries: response.chart_data.large_all_industries[index],
          large_manufacturing: response.chart_data.large_manufacturing[index],
          large_non_manufacturing: response.chart_data.large_non_manufacturing[index],
          medium_all_industries: response.chart_data.medium_all_industries[index],
          small_all_industries: response.chart_data.small_all_industries[index],
        }))

        setRawData(chartData)
        if (response.next_release) {
          setNextRelease(response.next_release)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'データの取得に失敗しました')
        console.error('Error loading BSI data:', err)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [currentSheet.sheetName, selectedPeriodType])

  const filteredData = useMemo(() => filterByPeriod(rawData, selectedPeriod), [rawData, selectedPeriod])

  const handlePrevious = () => {
    setCurrentSheetIndex((prev) => (prev - 1 + SHEETS.length) % SHEETS.length)
  }

  const handleNext = () => {
    setCurrentSheetIndex((prev) => (prev + 1) % SHEETS.length)
  }

  const title = `法人企業景気予測調査 ${currentSheet.displayName} - ${currentPeriodLabel}`

  if (loading) {
    return <LoadingChart title={title} />
  }

  if (error) {
    return (
      <ChartContainer title={title} showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  return (
    <div id="japan-bsi-unified-chart">
      <ChartContainer
        title={title}
        selectedPeriod={selectedPeriod}
        onPeriodChange={setSelectedPeriod}
        dataSource="財務省"
        sourceUrl="https://www.mof.go.jp/pri/reference/bos/index.htm"
        extra={
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {/* ページング */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Button icon={<LeftOutlined />} onClick={handlePrevious} disabled={currentSheetIndex === 0} size="small" />
              <span style={{ fontSize: '12px', color: '#8c8c8c', minWidth: '40px', textAlign: 'center' }}>
                {currentSheetIndex + 1}/{SHEETS.length}
              </span>
              <Button
                icon={<RightOutlined />}
                onClick={handleNext}
                disabled={currentSheetIndex === SHEETS.length - 1}
                size="small"
              />
            </div>
            {/* 次回発表 */}
            {nextRelease && formatNextRelease(nextRelease) && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                color: TEXT_COLORS.secondary,
              }}>
                <CalendarOutlined />
                <span>次回発表: {formatNextRelease(nextRelease)}</span>
              </div>
            )}
          </div>
        }
      >
        {/* Period Type Tabs */}
        <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'center' }}>
          <Segmented
            options={PERIOD_TYPES.map((p) => ({ label: p.label, value: p.type }))}
            value={selectedPeriodType}
            onChange={(value) => setSelectedPeriodType(value as PeriodType)}
          />
        </div>

        {/* Chart */}
        {filteredData.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>データがありません</div>
        ) : (
          <ZoomableChart
            data={filteredData}
            dataKey="large_all_industries"
            height={400}
            color="#1890ff"
            strokeWidth={2.5}
            name="大企業 全産業"
            showZeroLine={true}
            zeroLineValue={0}
            connectNulls={true}
            enableDynamicTicks={true}
            initialHiddenLines={['medium_all_industries', 'small_all_industries']}
            tooltipFormatter={(value: number) => `${value.toFixed(1)}`}
            tooltipLabelFormatter={(label: string) => {
              const date = new Date(label)
              const year = date.getFullYear()
              const month = date.getMonth() + 1
              const quarter = Math.ceil(month / 3)
              return `${year} Q${quarter}`
            }}
            xAxisTickFormatter={formatQuarterLabel}
            yAxisLabel="BSI (ポイント)"
            domain={['dataMin - 5', 'dataMax + 5']}
            additionalLines={[
              { dataKey: 'large_manufacturing', color: '#52c41a', name: '大企業 製造業', strokeWidth: 2.5 },
              { dataKey: 'large_non_manufacturing', color: '#fa8c16', name: '大企業 非製造業', strokeWidth: 2.5 },
              { dataKey: 'medium_all_industries', color: '#722ed1', name: '中堅企業 全産業', strokeWidth: 2 },
              { dataKey: 'small_all_industries', color: '#eb2f96', name: '中小企業 全産業', strokeWidth: 2 },
            ]}
          />
        )}
      </ChartContainer>
    </div>
  )
}
