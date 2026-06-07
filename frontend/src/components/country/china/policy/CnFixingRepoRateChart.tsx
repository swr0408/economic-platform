/**
 * China Fixing Repo Rate チャートコンポーネント
 *
 * FR001 / FR007 / FR014 / FDR001 / FDR007 / FDR014 の時系列を表示。
 *
 * データソース:
 * - backend/data/excel/Fixing_Repo_Rate_Historical_Data_{yyyy}.xlsx
 * - chinamoney.com.cn（毎日当年ファイルを更新）
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
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// =============================================================================
// 型定義
// =============================================================================

interface FrrRecord {
  date: string
  FR001: number | null
  FR007: number | null
  FR014: number | null
  FDR001: number | null
  FDR007: number | null
  FDR014: number | null
}

interface FrrApiResponse {
  data: FrrRecord[]
  latest: FrrRecord | null
  metadata: Record<string, unknown>
}

type GroupMode = 'fr' | 'fdr'

// =============================================================================
// カラー設定
// =============================================================================
const COLOR_001 = '#ef4444'   // 赤  - O/N
const COLOR_007 = '#f97316'   // オレンジ - 7日
const COLOR_014 = '#eab308'   // 黄  - 14日

const COLOR_FDR001 = '#3b82f6'  // 青  - FDR O/N
const COLOR_FDR007 = '#8b5cf6'  // 紫  - FDR 7日
const COLOR_FDR014 = '#06b6d4'  // シアン - FDR 14日

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

function CnFixingRepoRateChart() {
  const isMaster = useIsMaster()
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(3)
  const [group, setGroup] = useState<GroupMode>('fr')
  const [loading, setLoading] = useState(true)
  const [apiData, setApiData] = useState<FrrApiResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async (forceRefresh = false) => {
    try {
      setLoading(true)
      setError(null)
      const url = `${API_BASE_URL}/api/china/pboc/fixing-repo-rate${forceRefresh ? '?force_refresh=true' : ''}`
      const resp = await fetch(url)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const json: FrrApiResponse = await resp.json()
      setApiData(json)
    } catch (e) {
      console.error('[CnFixingRepoRate] fetch error:', e)
      setError('データの取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const records: FrrRecord[] = apiData?.data ?? []
  const latest = apiData?.latest ?? null

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(records, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2022,
  })

  // ローディング
  if (loading) {
    return <LoadingChart title="Fixing Repo Rate (FR / FDR)" />
  }

  // エラー / データなし
  if (error || records.length === 0) {
    return (
      <div id="fixing-repo-rate">
        <ChartContainer title="Fixing Repo Rate (FR / FDR)" showPeriodSelector={false} showDataSource={false}>
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

  // 表示する lines
  const linesByGroup = {
    fr: [
      { dataKey: 'FR001', color: COLOR_001,  name: 'FR001 (O/N)' },
      { dataKey: 'FR007', color: COLOR_007,  name: 'FR007 (7D)'  },
      { dataKey: 'FR014', color: COLOR_014,  name: 'FR014 (14D)' },
    ],
    fdr: [
      { dataKey: 'FDR001', color: COLOR_FDR001, name: 'FDR001 (O/N)' },
      { dataKey: 'FDR007', color: COLOR_FDR007, name: 'FDR007 (7D)'  },
      { dataKey: 'FDR014', color: COLOR_FDR014, name: 'FDR014 (14D)' },
    ],
  }

  // 最新値表示アイテム
  const latestItems =
    group === 'fr'
      ? [
          { label: 'FR001', value: latest?.FR001 ?? null, color: COLOR_001,  unit: '%', decimals: 4 },
          { label: 'FR007', value: latest?.FR007 ?? null, color: COLOR_007,  unit: '%', decimals: 4 },
          { label: 'FR014', value: latest?.FR014 ?? null, color: COLOR_014,  unit: '%', decimals: 4 },
        ]
      : [
          { label: 'FDR001', value: latest?.FDR001 ?? null, color: COLOR_FDR001, unit: '%', decimals: 4 },
          { label: 'FDR007', value: latest?.FDR007 ?? null, color: COLOR_FDR007, unit: '%', decimals: 4 },
          { label: 'FDR014', value: latest?.FDR014 ?? null, color: COLOR_FDR014, unit: '%', decimals: 4 },
        ]

  return (
    <div id="fixing-repo-rate">
      <ChartContainer
        title="Fixing Repo Rate (FR / FDR)"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国外汇交易中心 (CFETS)"
        sourceUrl="https://www.chinamoney.com.cn/english/bmkfrr/"
        handbookId="fixing-repo-rate"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={latest?.date}
          dateFormatter={formatDateFull}
        />

        {/* FR / FDR 切替 + データ比較ボタン（同一行） */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup
            options={[
              { mode: 'fr'  as GroupMode, label: 'FR（銀行間）' },
              { mode: 'fdr' as GroupMode, label: 'FDR（預金機関間）' },
            ]}
            currentMode={group}
            onChange={setGroup}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() =>
                window.open('/compare?s=cn_fixing_fr007&s=cn_fixing_fdr007', '_blank')
              }
            >
              データ比較
            </Button>
          </Tooltip>
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
export default withVisibility(CnFixingRepoRateChart, 'special')
