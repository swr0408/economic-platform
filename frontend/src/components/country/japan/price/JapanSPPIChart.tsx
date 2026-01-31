/**
 * Japan SPPI Chart Component
 * 企業向けサービス価格指数チャート
 *
 * データ項目:
 * - yoy: 前年同月比 (%)
 *
 * Note: FMPにマッピングがないため、マーケットインパクトタブは非表示
 */

import { useEffect, useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  CHART_COLORS,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import {
  fetchSPPIData,
  type SPPIResponse,
  type SPPIDataPoint,
} from '../../../../utils/japan/sppiApi'

// =============================================================================
// 型定義
// =============================================================================

// カラー設定
const COLORS = {
  yoy: CHART_COLORS.primary,
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function JapanSPPIChart() {
  const [data, setData] = useState<SPPIResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchSPPIData()
        if (res.error) {
          setError(res.error)
        } else {
          setData(res)
        }
      } catch (err) {
        console.error('Error loading SPPI data:', err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  // データを変換
  const chartData = useMemo(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: SPPIDataPoint) => d.yoy !== null)
      .map((d: SPPIDataPoint) => ({
        date: d.date,
        yoy: d.yoy,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2019,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (loading) {
    return <LoadingChart title="企業向けサービス価格指数（SPPI）" />
  }

  // エラー状態
  if (error) {
    return (
      <ChartContainer title="企業向けサービス価格指数（SPPI）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="企業向けサービス価格指数（SPPI）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  // 次回発表日のフォーマット
  const formatNextRelease = () => {
    if (!data?.next_release) return null
    const nr = data.next_release
    if (nr.datetime_jst) {
      const dt = new Date(nr.datetime_jst)
      return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`
    }
    if (nr.date) {
      const dt = new Date(nr.date)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    }
    return null
  }

  return (
    <div id="japan-sppi-chart">
      <ChartContainer
        title="企業向けサービス価格指数（SPPI）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="日本銀行"
        sourceUrl="https://www.boj.or.jp/statistics/pi/cspi_release/index.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '前年比',
              value: latest?.yoy,
              color: COLORS.yoy,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
          nextRelease={data?.next_release ? { date: formatNextRelease() || '' } : undefined}
        />

        {/* 期間セレクタ + 比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=japan_sppi_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'yoy', color: COLORS.yoy, name: '企業向けサービス価格指数（前年比）', hide: hiddenSeries.has('yoy') },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateLabelJP}
          tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
