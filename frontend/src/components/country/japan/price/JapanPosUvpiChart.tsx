/**
 * Japan POS-UVPI Chart Component
 * 消費者購買単価指数（SRI一橋大学）チャート
 *
 * データ項目:
 * - chg_uvpi_total: POS-UVPI 週次変化率 (%)
 */

import { useEffect, useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import {
  fetchPosUvpiData,
  type PosUvpiResponse,
  type PosUvpiDataPoint,
} from '../../../../utils/japan/posUvpiApi'

// =============================================================================
// 定数
// =============================================================================

// カラー設定
const COLORS = {
  uvpi: '#1890ff',
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function JapanPosUvpiChart() {
  const [data, setData] = useState<PosUvpiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<number | 'default' | 'all'>(10)

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchPosUvpiData()
        if (res.error) {
          setError(res.error)
        } else {
          setData(res)
        }
      } catch (err) {
        console.error('Error loading POS-UVPI data:', err)
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
      .filter((d: PosUvpiDataPoint) => d.chg_uvpi_total !== null && d.chg_uvpi_total !== undefined)
      .map((d: PosUvpiDataPoint) => ({
        date: d.date,
        chg_uvpi_total: d.chg_uvpi_total,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (loading) {
    return <LoadingChart title="POS-UVPI（週次）" />
  }

  // エラー状態
  if (error) {
    return (
      <ChartContainer title="POS-UVPI（週次）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="POS-UVPI（週次）" showPeriodSelector={false} showDataSource={false}>
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
    <div id="japan-pos-uvpi-chart">
      <ChartContainer
        title="POS-UVPI"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="一橋大学経済研究所"
        sourceUrl="https://risk.ier.hit-u.ac.jp/Japanese/nei/posuvpi.html"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: 'SRI一橋大学消費者購買単価指数',
              value: latest?.chg_uvpi_total,
              color: COLORS.uvpi,
              format: 'percent',
              decimals: 4,
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
          nextRelease={data?.next_release ? { date: formatNextRelease() || '' } : undefined}
        />

        {/* 期間セレクター + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=japan_pos_uvpi', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'chg_uvpi_total', color: COLORS.uvpi, name: 'POS-UVPI' },
          ]}
          yAxisFormatter={(v: number) => `${v.toFixed(2)}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateLabelJP}
          tooltipValueFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(4)}%`}
          showZeroLine={true}
        />
      </ChartContainer>
    </div>
  )
}
