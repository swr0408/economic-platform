/**
 * Japan S&P Global PMIチャートコンポーネント
 *
 * 製造業PMI、サービス業PMI、総合PMIを表示
 *
 * データソース:
 * - S&P Global (Markit)
 *
 * 発表スケジュール:
 * - 速報値: 毎月第3週（23日前後）
 * - 確報値: 毎月第1週（1日前後）
 */
import { useState, useMemo, useEffect } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import {
  fetchJapanPMIData,
  type JapanPMIResponse,
} from '../../../../utils/japan/jpPmiApi'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
  manufacturing: number | null
  services: number | null
  composite: number | null
  [key: string]: unknown
}

// カラー設定
const COLORS = {
  manufacturing: '#1890ff', // 青
  services: '#52c41a',      // 緑
  composite: '#722ed1',     // 紫
}

const DEFAULT_PERIOD: PeriodValue = 'default'
const DEFAULT_START_DATE = '2020-01-01'

// =============================================================================
// ユーティリティ関数
// =============================================================================

const parseDate = (value: string): Date | null => {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const filterByPeriod = (
  data: ChartDataPoint[],
  period: PeriodValue
): ChartDataPoint[] => {
  if (period === 'all') {
    return [...data].sort((a, b) => {
      const dateA = parseDate(a.date)
      const dateB = parseDate(b.date)
      if (!dateA || !dateB) return 0
      return dateA.getTime() - dateB.getTime()
    })
  }

  const now = new Date()
  let startDate: Date

  if (period === 'default') {
    startDate = new Date(DEFAULT_START_DATE)
  } else if (typeof period === 'number') {
    startDate = new Date(now.getFullYear() - period, now.getMonth(), now.getDate())
  } else {
    return data
  }

  return data
    .filter((point) => {
      const pointDate = parseDate(point.date)
      return pointDate && pointDate >= startDate
    })
    .sort((a, b) => {
      const dateA = parseDate(a.date)
      const dateB = parseDate(b.date)
      if (!dateA || !dateB) return 0
      return dateA.getTime() - dateB.getTime()
    })
}

const formatMonthLabel = (dateStr: string): string => {
  const date = parseDate(dateStr)
  if (!date) return dateStr
  const year = date.getFullYear() % 100
  const month = date.getMonth() + 1
  return `'${year.toString().padStart(2, '0')}/${month.toString().padStart(2, '0')}`
}

const formatDateForDisplay = (dateStr: string): string => {
  const date = parseDate(dateStr)
  if (!date) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function JapanPMIChart() {
  const [response, setResponse] = useState<JapanPMIResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(DEFAULT_PERIOD)
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchJapanPMIData()

        if (res.error) {
          setError(res.error)
        } else {
          setResponse(res)
        }
      } catch (err) {
        console.error('Error loading Japan PMI data:', err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  // 3系列のデータをマージして1つのチャートデータに変換
  const chartData = useMemo(() => {
    if (!response) return []

    const mfgData = response.manufacturing?.data || []
    const svcData = response.services?.data || []
    const cmpData = response.composite?.data || []

    // 全日付を収集
    const allDates = new Set<string>()
    mfgData.forEach((d) => allDates.add(d.date))
    svcData.forEach((d) => allDates.add(d.date))
    cmpData.forEach((d) => allDates.add(d.date))

    // 日付順にソート
    const sortedDates = Array.from(allDates).sort(
      (a, b) => new Date(a).getTime() - new Date(b).getTime()
    )

    // 各日付に対してデータをマージ
    const mfgMap = new Map(mfgData.map((d) => [d.date, d.value]))
    const svcMap = new Map(svcData.map((d) => [d.date, d.value]))
    const cmpMap = new Map(cmpData.map((d) => [d.date, d.value]))

    return sortedDates.map((date) => ({
      date,
      value: mfgMap.get(date) ?? null,
      manufacturing: mfgMap.get(date) ?? null,
      services: svcMap.get(date) ?? null,
      composite: cmpMap.get(date) ?? null,
    }))
  }, [response])

  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, selectedPeriod)
  }, [chartData, selectedPeriod])

  // 最新値を取得
  const mfgLatest = response?.manufacturing?.latest
  const svcLatest = response?.services?.latest
  const cmpLatest = response?.composite?.latest

  const hasData = chartData.length > 0
  const showChart = hasData && filteredData.length > 0

  if (loading) {
    return <LoadingChart title="S&P Global PMI（日本）" />
  }

  if (error) {
    return (
      <ChartContainer title="S&P Global PMI（日本）" showDataSource={false} showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="S&P Global PMI（日本）" showDataSource={false} showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  const compareUrl = '/compare?s=jp_sp_manufacturing_pmi&s=jp_sp_services_pmi&s=jp_sp_composite_pmi'

  return (
    <div id="japan-pmi-chart">
      <ChartContainer
        title="S&P Global PMI（日本）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="S&P Global"
        sourceUrl="https://www.pmi.spglobal.com/Public/Release/PressReleases"
      >
        {/* 最新値表示（3系列） */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '16px',
            alignItems: 'center',
            padding: '12px 0',
            borderBottom: '1px solid #f0f0f0',
            marginBottom: '8px',
          }}
        >
          {/* 製造業PMI */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.manufacturing,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>製造業</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.manufacturing }}>
              {mfgLatest?.value?.toFixed(1) ?? '-'}
            </span>
          </div>

          {/* サービス業PMI */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.services,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>サービス業</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.services }}>
              {svcLatest?.value?.toFixed(1) ?? '-'}
            </span>
          </div>

          {/* 総合PMI */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.composite,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>総合</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.composite }}>
              {cmpLatest?.value?.toFixed(1) ?? '-'}
            </span>
          </div>

          {/* 日付表示 */}
          <div
            style={{
              marginLeft: 'auto',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'flex-end',
              fontSize: 11,
              color: '#8c8c8c',
            }}
          >
            {mfgLatest?.date && <div>{formatDateForDisplay(mfgLatest.date)}</div>}
            {response?.next_release && (
              <div>
                次回発表: {response.next_release.date}
              </div>
            )}
          </div>
        </div>

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 期間セレクタ + 比較ボタン */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 8,
                    }}
                  >
                    <PeriodSelector
                      onPeriodChange={setSelectedPeriod}
                      selectedPeriod={selectedPeriod}
                    />
                    <Tooltip title="比較ページを開く（S&P PMI）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(compareUrl, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {showChart && (
                    <ZoomableChart
                      data={filteredData}
                      dataKey="manufacturing"
                      name="製造業PMI"
                      color={COLORS.manufacturing}
                      height={400}
                      strokeWidth={2.5}
                      xAxisTickFormatter={formatMonthLabel}
                      domain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={false}
                      showFiftyLine={true}
                      fiftyLineValue={50}
                      connectNulls={true}
                      enableDynamicTicks={true}
                      tooltipFormatter={(value: number) => `${value.toFixed(1)}`}
                      tooltipLabelFormatter={(label: string) => {
                        const date = parseDate(String(label))
                        if (!date) return label
                        return `${date.getFullYear()}年${date.getMonth() + 1}月`
                      }}
                      additionalLines={[
                        {
                          dataKey: 'services',
                          color: COLORS.services,
                          name: 'サービス業PMI',
                          strokeWidth: 2.5,
                        },
                        {
                          dataKey: 'composite',
                          color: COLORS.composite,
                          name: '総合PMI',
                          strokeWidth: 2.5,
                        },
                      ]}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="jp_sp_manufacturing_pmi" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
