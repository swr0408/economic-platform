/**
 * Central Parity Rate（基準値・Fixing）チャートコンポーネント
 *
 * USD/CNY 基準値（CFETS発表）とスポットレート（Yahoo Finance）を重ねて表示。
 *
 * データソース:
 * - backend/data/csv_import/Central_Parity_Historical_Data_{yyyy}.xlsx
 * - chinamoney.com.cn API（毎日当年ファイルを更新）
 * - yfinance (CNY=X) USD/CNYスポットレート
 *
 * FMPマッピング: なし（マーケットインパクトタブなし）
 */
import { useState, useEffect } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import { useIsMaster } from '../../../../hooks/useIsMaster'
import { withVisibility } from '../../../common/withVisibility'

import {
  usePeriodFiltering,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
  LatestValueBox,
} from '../../usa/common/ChartComponents'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// =============================================================================
// 型定義
// =============================================================================

interface CentralParityRecord {
  date: string
  fixing: number | null
  spot: number | null
}

interface CentralParityLatest {
  fixing_date: string | null
  fixing: number | null
  spot_date: string | null
  spot: number | null
}

interface CentralParityApiResponse {
  data: CentralParityRecord[]
  latest: CentralParityLatest | null
  metadata: Record<string, unknown>
}

// =============================================================================
// カラー設定
// =============================================================================
const COLOR_FIXING = '#DC143C'  // クリムゾンレッド（基準値）
const COLOR_SPOT   = '#3b82f6'  // ブルー（スポット）

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
  const [year, month, day] = dateStr.split('-')
  return `${year}年${parseInt(month)}月${parseInt(day)}日`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

function CnCentralParityChart() {
  const isMaster = useIsMaster()
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(3)
  const [loading, setLoading] = useState(true)
  const [apiData, setApiData] = useState<CentralParityApiResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async (forceRefresh = false) => {
    try {
      setLoading(true)
      setError(null)
      const url = `${API_BASE_URL}/api/china/pboc/central-parity${forceRefresh ? '?force_refresh=true' : ''}`
      const resp = await fetch(url)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const json: CentralParityApiResponse = await resp.json()
      setApiData(json)
    } catch (e) {
      console.error('[CnCentralParity] fetch error:', e)
      setError('データの取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const records: CentralParityRecord[] = apiData?.data ?? []
  const latest = apiData?.latest ?? null

  const filteredData = usePeriodFiltering(records, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2022,
  })

  if (loading) {
    return <LoadingChart title="Central Parity Rate（USD/CNY基準値）" />
  }

  if (error || records.length === 0) {
    return (
      <div id="central-parity">
        <ChartContainer title="Central Parity Rate（USD/CNY基準値）" showPeriodSelector={false} showDataSource={false}>
          {error ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
              {error}
              {isMaster && (
                <div style={{ marginTop: 12 }}>
                  <Button size="small" onClick={() => fetchData(true)}>再取得</Button>
                </div>
              )}
            </div>
          ) : (
            <NoDataMessage />
          )}
        </ChartContainer>
      </div>
    )
  }

  const latestItems = [
    {
      label: '基準値(Fixing)',
      value: latest?.fixing ?? null,
      color: COLOR_FIXING,
      unit: '',
      decimals: 4,
    },
    {
      label: 'スポット',
      value: latest?.spot ?? null,
      color: COLOR_SPOT,
      unit: '',
      decimals: 4,
    },
  ]

  const latestDate = latest?.fixing_date || latest?.spot_date || undefined

  return (
    <div id="central-parity">
      <ChartContainer
        title="Central Parity Rate（USD/CNY基準値）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国外汇交易中心 (CFETS) / Yahoo Finance"
        sourceUrl="https://www.chinamoney.com.cn/english/bmkcpr/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latestDate}
          dateFormatter={formatDateFull}
        />

        {/* データ比較ボタン（右寄せ） */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() =>
                window.open('/compare?s=cn_central_parity', '_blank')
              }
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* 折れ線グラフ（基準値 + スポット） */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'fixing', color: COLOR_FIXING, name: '基準値(Fixing)' },
            { dataKey: 'spot',   color: COLOR_SPOT,   name: 'USD/CNYスポット' },
          ]}
          yAxisFormatter={(v) => `${v.toFixed(2)}`}
          yDomain={['dataMin - 0.05', 'dataMax + 0.05']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v) => `${v.toFixed(4)}`}
          showLegend={true}
        />
      </ChartContainer>
    </div>
  )
}

// special 限定 (一般ユーザには非表示)
export default withVisibility(CnCentralParityChart, 'special')
