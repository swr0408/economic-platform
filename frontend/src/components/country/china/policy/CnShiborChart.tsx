/**
 * SHIBOR（上海銀行間取引金利）チャートコンポーネント
 *
 * O/N, 1W, 2W, 1M, 3M, 6M, 9M, 1Y の8系列を表示。
 * 短期（O/N〜1M）/ 長期（3M〜1Y）の2グループを ViewModeButtonGroup で切替。
 *
 * データソース:
 * - backend/data/excel/Shibor_Historical_Data_{yyyy}.xlsx
 * - shibor.org（毎日当年ファイルを更新）
 *
 * FMPマッピング: なし
 */
import { useState, useEffect } from 'react'
import { Button } from 'antd'
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
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// =============================================================================
// 型定義
// =============================================================================

interface ShiborRecord {
  date: string
  ON:  number | null
  '1W': number | null
  '2W': number | null
  '1M': number | null
  '3M': number | null
  '6M': number | null
  '9M': number | null
  '1Y': number | null
}

interface ShiborApiResponse {
  data: ShiborRecord[]
  latest: ShiborRecord | null
  metadata: Record<string, unknown>
}

type GroupMode = 'short' | 'long'

// =============================================================================
// カラー設定（テナー順: 短 → 長）
// =============================================================================
const COLORS: Record<string, string> = {
  ON:   '#ef4444',  // 赤
  '1W': '#f97316',  // オレンジ
  '2W': '#eab308',  // 黄
  '1M': '#22c55e',  // 緑
  '3M': '#06b6d4',  // シアン
  '6M': '#3b82f6',  // 青
  '9M': '#8b5cf6',  // 紫
  '1Y': '#ec4899',  // ピンク
}

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

function CnShiborChart() {
  const isMaster = useIsMaster()
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(3)
  const [group, setGroup] = useState<GroupMode>('short')
  const [loading, setLoading] = useState(true)
  const [apiData, setApiData] = useState<ShiborApiResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async (forceRefresh = false) => {
    try {
      setLoading(true)
      setError(null)
      const url = `${API_BASE_URL}/api/china/pboc/shibor${forceRefresh ? '?force_refresh=true' : ''}`
      const resp = await fetch(url)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const json: ShiborApiResponse = await resp.json()
      setApiData(json)
    } catch (e) {
      console.error('[CnShibor] fetch error:', e)
      setError('データの取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const records: ShiborRecord[] = apiData?.data ?? []
  const latest = apiData?.latest ?? null

  const filteredData = usePeriodFiltering(records, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2022,
  })

  if (loading) {
    return <LoadingChart title="SHIBOR（上海銀行間取引金利）" />
  }

  if (error || records.length === 0) {
    return (
      <div id="shibor">
        <ChartContainer title="SHIBOR（上海銀行間取引金利）" showPeriodSelector={false} showDataSource={false}>
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

  // 短期 / 長期グループ
  const linesByGroup = {
    short: [
      { dataKey: 'ON',  color: COLORS['ON'],  name: 'O/N' },
      { dataKey: '1W',  color: COLORS['1W'],  name: '1W'  },
      { dataKey: '2W',  color: COLORS['2W'],  name: '2W'  },
      { dataKey: '1M',  color: COLORS['1M'],  name: '1M'  },
    ],
    long: [
      { dataKey: '3M',  color: COLORS['3M'],  name: '3M'  },
      { dataKey: '6M',  color: COLORS['6M'],  name: '6M'  },
      { dataKey: '9M',  color: COLORS['9M'],  name: '9M'  },
      { dataKey: '1Y',  color: COLORS['1Y'],  name: '1Y'  },
    ],
  }

  const latestItems =
    group === 'short'
      ? [
          { label: 'O/N', value: latest?.ON    ?? null, color: COLORS['ON'],  unit: '%', decimals: 4 },
          { label: '1W',  value: latest?.['1W'] ?? null, color: COLORS['1W'], unit: '%', decimals: 4 },
          { label: '2W',  value: latest?.['2W'] ?? null, color: COLORS['2W'], unit: '%', decimals: 4 },
          { label: '1M',  value: latest?.['1M'] ?? null, color: COLORS['1M'], unit: '%', decimals: 4 },
        ]
      : [
          { label: '3M',  value: latest?.['3M'] ?? null, color: COLORS['3M'], unit: '%', decimals: 4 },
          { label: '6M',  value: latest?.['6M'] ?? null, color: COLORS['6M'], unit: '%', decimals: 4 },
          { label: '9M',  value: latest?.['9M'] ?? null, color: COLORS['9M'], unit: '%', decimals: 4 },
          { label: '1Y',  value: latest?.['1Y'] ?? null, color: COLORS['1Y'], unit: '%', decimals: 4 },
        ]

  return (
    <div id="shibor">
      <ChartContainer
        title="SHIBOR（上海銀行間取引金利）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国外汇交易中心 (CFETS)"
        sourceUrl="https://www.shibor.org/english/bmkshb/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latest?.date}
          dateFormatter={formatDateFull}
        />

        {/* 短期 / 長期切替 */}
        <div style={{ marginBottom: 8 }}>
          <ViewModeButtonGroup
            options={[
              { mode: 'short' as GroupMode, label: '短期（O/N〜1M）' },
              { mode: 'long'  as GroupMode, label: '長期（3M〜1Y）'  },
            ]}
            currentMode={group}
            onChange={setGroup}
          />
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* 折れ線グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={linesByGroup[group]}
          yAxisFormatter={(v) => `${v.toFixed(2)}%`}
          yDomain={['dataMin - 0.1', 'dataMax + 0.1']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v) => `${v.toFixed(4)}%`}
          showLegend={true}
        />
      </ChartContainer>
    </div>
  )
}

// special 限定 (一般ユーザには非表示)
export default withVisibility(CnShiborChart, 'special')
