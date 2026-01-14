/**
 * 設備投資チャート
 *
 * データソース: e-Stat（財務省・法人企業統計調査）
 * statsDataId: 0003060191
 * 更新: 3月、6月、9月、12月の1日〜5日頃
 *
 * 表示: 前年比（%）
 */
import { useState, useEffect, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'

// USA共通モジュールを流用
import {
  formatPercent,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
} from '../../usa/common/ChartComponents'
import {
  LATEST_VALUE_BOX_STYLE,
  TEXT_COLORS,
} from '../../usa/common/chartConstants'

import {
  fetchCapitalInvestmentData,
  type CapitalInvestmentDataPoint,
  type NextRelease,
} from '../../../../api/capitalInvestmentApi'

// チャートデータ型
interface InvestmentChartData {
  date: string
  value: number
  originalDate: string
  [key: string]: string | number | null | undefined
}

// グラフの色
const COLORS = {
  yoy: '#52c41a',  // 緑
}

// 四半期日付をパース
const parseQuarterDate = (dateStr: string): Date | null => {
  const match = dateStr.match(/^(\d{4})-Q(\d)$/)
  if (!match) return null

  const year = parseInt(match[1])
  const quarter = parseInt(match[2])

  // Q1->Mar, Q2->Jun, Q3->Sep, Q4->Dec
  const monthMap: { [key: number]: number } = { 1: 2, 2: 5, 3: 8, 4: 11 }
  const month = monthMap[quarter] || 2

  return new Date(year, month, 1)
}

// 期間フィルタリング（四半期データ用）
const filterByPeriod = (
  data: InvestmentChartData[],
  period: PeriodValue,
  defaultStartYear: number = 2015
): InvestmentChartData[] => {
  if (period === 'all') {
    return data
  }

  let cutoffDate: Date
  if (period === 'default') {
    cutoffDate = new Date(defaultStartYear, 0, 1)
  } else if (typeof period === 'number') {
    cutoffDate = new Date()
    cutoffDate.setFullYear(cutoffDate.getFullYear() - period)
  } else {
    cutoffDate = new Date(defaultStartYear, 0, 1)
  }

  return data.filter(item => {
    const itemDate = new Date(item.date)
    return itemDate >= cutoffDate
  })
}

/**
 * APIから取得したデータをチャート用に変換
 */
function transformToChartData(data: CapitalInvestmentDataPoint[]): InvestmentChartData[] {
  return data
    .filter(item => item.yoy_growth !== null && item.yoy_growth !== undefined)
    .map((item) => {
      // YYYY-Qn format to Date
      const parsed = parseQuarterDate(item.date)
      if (!parsed) {
        return null
      }

      return {
        date: parsed.toISOString(),
        value: item.yoy_growth as number,
        originalDate: item.date,
      }
    })
    .filter((item): item is InvestmentChartData => item !== null)
}

// 四半期日付フォーマット（YYYY-Qn -> YYYY/Qn）
const formatQuarterLabel = (dateStr: string): string => {
  try {
    return dateStr.replace('-', '/')
  } catch {
    return dateStr
  }
}

// 次回発表日時フォーマット関数
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

  if (nextRelease.date && nextRelease.time_jst) {
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

const CapitalInvestmentChart: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rawData, setRawData] = useState<CapitalInvestmentDataPoint[]>([])
  const [nextRelease, setNextRelease] = useState<NextRelease | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetchCapitalInvestmentData()
        if (response.error) {
          setError(response.error)
        } else {
          setRawData(response.data)
          setNextRelease(response.next_release || null)
        }
      } catch (err) {
        console.error('Error fetching Capital Investment data:', err)
        setError('データの取得に失敗しました')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // チャートデータに変換
  const yoyChartData = useMemo<InvestmentChartData[]>(() => {
    if (!rawData || rawData.length === 0) return []
    return transformToChartData(rawData)
  }, [rawData])

  // formatPercent共通関数を使用（小数点1桁）
  const formatPercentage = (value: number) => formatPercent(value, 1)

  // 期間フィルタリング
  const filteredYoYData = useMemo(() => {
    return filterByPeriod(yoyChartData, currentPeriod, 2015)
  }, [yoyChartData, currentPeriod])

  const hasData = yoyChartData.length > 0

  if (loading) {
    return <LoadingChart title="設備投資（前年比）" />
  }

  if (error) {
    return (
      <ChartContainer title="設備投資（前年比）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="設備投資（前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestYoY = yoyChartData.length > 0 ? yoyChartData[yoyChartData.length - 1] : null

  return (
    <div id="japan-capital-investment-chart">
      <ChartContainer
        title="設備投資（前年比）"
        showPeriodSelector={false}
        dataSource="財務省"
        sourceUrl="https://www.mof.go.jp/pri/reference/ssc/results/data.htm"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {latestYoY?.originalDate && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatQuarterLabel(latestYoY.originalDate)}
              </span>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>前年比:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.yoy }}>
                {latestYoY?.value?.toFixed(1) ?? '-'}%
              </span>
            </div>
          </div>

          {/* 右側: 次回発表 */}
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

        {/* 期間セレクター */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=japan_capital_investment', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        <ZoomableChart
          data={filteredYoYData}
          dataKey="value"
          color={COLORS.yoy}
          name="設備投資（前年比）"
          height={400}
          tickFormatter={formatPercentage}
          tooltipFormatter={formatPercentage}
          tooltipLabelFormatter={(dateStr) => {
            const date = new Date(dateStr)
            const year = date.getFullYear()
            const month = date.getMonth()
            const quarter = Math.floor(month / 3) + 1
            return `${year}年 Q${quarter}`
          }}
          xAxisTickFormatter={(dateStr) => {
            const date = new Date(dateStr)
            const year = date.getFullYear()
            const month = date.getMonth()
            const quarter = Math.floor(month / 3) + 1
            return `${year}/Q${quarter}`
          }}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
        />
      </ChartContainer>
    </div>
  )
}

export default CapitalInvestmentChart
