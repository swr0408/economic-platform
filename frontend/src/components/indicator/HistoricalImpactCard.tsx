/**
 * 過去の発表インパクトカード
 *
 * 過去1年分の発表時のマーケット反応を表示
 * - 単独表示: 1つの発表を選択してチャート表示
 * - オーバーレイ比較: 複数の発表を重ねて比較（発表時刻を0点として正規化）
 */
import { useState, useEffect, useMemo } from 'react'
import { Select, Segmented, Space, Empty, Spin, Checkbox, Button } from 'antd'
import { LineChartOutlined, BarChartOutlined, CloseOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import CandlestickChart from '../common/CandlestickChart'
import LineChart from '../common/LineChart'
import ChartContainer from '../common/ChartContainer'

// ダークテーマカラー
const DARK_THEME = {
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
  releaseMarker: '#fbbf24', // 発表時刻マーカー（黄）
}

// オーバーレイ用の色パレット
const OVERLAY_COLORS = [
  '#3b82f6', // blue
  '#22c55e', // green
  '#f59e0b', // amber
  '#ef4444', // red
  '#a855f7', // purple
]

// 分数を「±hh時間mm分」形式にフォーマット
function formatMinutesToTime(minutes: number): string {
  const sign = minutes >= 0 ? '+' : '-'
  const absMinutes = Math.abs(minutes)
  const hours = Math.floor(absMinutes / 60)
  const mins = absMinutes % 60

  if (hours === 0) {
    return `${sign}${mins}分`
  } else if (mins === 0) {
    return `${sign}${hours}時間`
  } else {
    return `${sign}${hours}時間${mins}分`
  }
}

// X軸のキリのいい目盛り位置を生成（分単位）
function generateXAxisTicks(interval: '1m' | '5m'): number[] {
  if (interval === '1m') {
    // 1分足: ±1時間なので、15分刻み
    return [-60, -45, -30, -15, 0, 15, 30, 45, 60]
  } else {
    // 5分足: ±24時間なので、6時間刻み
    return [-1440, -1080, -720, -360, 0, 360, 720, 1080, 1440]
  }
}

interface Release {
  release_datetime: string
  release_date: string
  period_label: string
  actual: number | null
  estimate: number | null
  previous: number | null
  surprise: number | null
  impact: string | null
}

interface ChartData {
  timestamp: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
}

interface CompareSeries {
  release_datetime: string
  label: string
  data: {
    minutes_from_release: number
    close: number
    change_pct: number
  }[]
}

interface HistoricalImpactCardProps {
  indicatorId: string
  indicatorName: string
  onClose?: () => void
}

// 銘柄リスト
const SYMBOLS = [
  { value: 'usdjpy', label: 'USD/JPY' },
  { value: 'eurusd', label: 'EUR/USD' },
  { value: 'gbpusd', label: 'GBP/USD' },
  { value: 'gold', label: 'ゴールド' },
  { value: 'sp500', label: 'S&P500' },
]

export default function HistoricalImpactCard({
  indicatorId,
  indicatorName,
  onClose,
}: HistoricalImpactCardProps) {
  const [mode, setMode] = useState<'single' | 'compare'>('single')
  const [selectedRelease, setSelectedRelease] = useState<string | null>(null)
  const [selectedReleases, setSelectedReleases] = useState<string[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState('usdjpy')
  const [interval, setInterval] = useState<'1m' | '5m'>('1m')

  // 発表履歴を取得
  const { data: releasesData, isLoading: isLoadingReleases } = useQuery({
    queryKey: ['market-impact-releases', indicatorId],
    queryFn: async () => {
      const res = await axios.get(`/api/market-impact/releases/${indicatorId}`)
      return res.data as { releases: Release[]; count: number }
    },
    staleTime: 5 * 60 * 1000,
  })

  // 最初の発表を選択
  useEffect(() => {
    if (releasesData?.releases?.length && !selectedRelease) {
      setSelectedRelease(releasesData.releases[0].release_datetime)
    }
  }, [releasesData, selectedRelease])

  // 単独表示用チャートデータ
  const { data: singleChartData, isLoading: isLoadingSingle } = useQuery({
    queryKey: ['market-impact-chart', selectedRelease, selectedSymbol, interval],
    queryFn: async () => {
      if (!selectedRelease) return null
      const res = await axios.get('/api/market-impact/chart', {
        params: {
          release_datetime: selectedRelease,
          symbol_id: selectedSymbol,
          interval,
        }
      })
      return res.data as {
        data: ChartData[]
        release_index: number | null
        count: number
      }
    },
    enabled: mode === 'single' && !!selectedRelease,
    staleTime: 5 * 60 * 1000,
  })

  // 比較用データ
  const { data: compareData, isLoading: isLoadingCompare } = useQuery({
    queryKey: ['market-impact-compare', selectedReleases, selectedSymbol, interval],
    queryFn: async () => {
      if (!selectedReleases.length) return null
      const res = await axios.get('/api/market-impact/compare', {
        params: {
          release_datetimes: selectedReleases.join(','),
          symbol_id: selectedSymbol,
          interval,
        }
      })
      return res.data as {
        series: CompareSeries[]
        count: number
      }
    },
    enabled: mode === 'compare' && selectedReleases.length > 0,
    staleTime: 5 * 60 * 1000,
  })

  // 比較用データをマージ
  const mergedCompareData = useMemo(() => {
    if (!compareData?.series?.length) return []

    // 全シリーズの分数を収集
    const allMinutes = new Set<number>()
    compareData.series.forEach(s => {
      s.data.forEach(d => allMinutes.add(d.minutes_from_release))
    })

    const minutesArray = Array.from(allMinutes).sort((a, b) => a - b)

    return minutesArray.map(minutes => {
      const point: Record<string, number | string> = { minutes }

      compareData.series.forEach((series, idx) => {
        const dataPoint = series.data.find(d => d.minutes_from_release === minutes)
        if (dataPoint) {
          point[`series_${idx}`] = dataPoint.change_pct
        }
      })

      return point
    })
  }, [compareData])

  // 発表日時のフォーマット（短縮版）
  const formatReleaseShort = (release: Release) => {
    const dt = new Date(release.release_datetime)
    return dt.toLocaleDateString('ja-JP', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  // 発表日時のフォーマット（月情報付き）
  const formatReleaseOption = (release: Release) => {
    const dateStr = formatReleaseShort(release)
    return `${dateStr}${release.period_label ? ` (${release.period_label})` : ''}`
  }

  // 比較用チェックボックス
  const handleCompareSelect = (datetime: string, checked: boolean) => {
    if (checked && selectedReleases.length < 5) {
      setSelectedReleases([...selectedReleases, datetime])
    } else {
      setSelectedReleases(selectedReleases.filter(d => d !== datetime))
    }
  }

  // 選択された発表の情報を取得
  const getSelectedReleaseInfo = (datetime: string): Release | undefined => {
    return releasesData?.releases?.find(r => r.release_datetime === datetime)
  }

  const isLoading = isLoadingReleases || (mode === 'single' ? isLoadingSingle : isLoadingCompare)

  // X軸の目盛り
  const xAxisTicks = generateXAxisTicks(interval)

  return (
    <ChartContainer
      title={`過去の発表インパクト - ${indicatorName}`}
      showPeriodSelector={false}
      extra={
        onClose ? (
          <Button
            type="text"
            icon={<CloseOutlined />}
            onClick={onClose}
            size="small"
          />
        ) : undefined
      }
    >
      {/* モード切替とコントロール */}
      <div style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <Segmented
            value={mode}
            onChange={(v) => setMode(v as 'single' | 'compare')}
            options={[
              { value: 'single', label: '単独表示', icon: <BarChartOutlined /> },
              { value: 'compare', label: 'オーバーレイ比較', icon: <LineChartOutlined /> },
            ]}
          />

          {mode === 'single' && (
            <Select
              value={selectedRelease}
              onChange={setSelectedRelease}
              style={{ width: 220 }}
              placeholder="発表日時を選択"
              options={releasesData?.releases?.map(r => ({
                value: r.release_datetime,
                label: formatReleaseOption(r),
              })) ?? []}
            />
          )}

          <Select
            value={selectedSymbol}
            onChange={setSelectedSymbol}
            style={{ width: 120 }}
            options={SYMBOLS}
          />

          <Segmented
            value={interval}
            onChange={(v) => setInterval(v as '1m' | '5m')}
            options={[
              { value: '1m', label: '1分足' },
              { value: '5m', label: '5分足' },
            ]}
          />
        </Space>
      </div>

      {/* 比較モード: 発表選択 */}
      {mode === 'compare' && releasesData?.releases && (
        <div
          style={{
            marginBottom: 16,
            padding: 12,
            backgroundColor: 'rgba(30, 41, 59, 0.5)',
            borderRadius: 8,
          }}
        >
          <div style={{ marginBottom: 8, color: DARK_THEME.textSecondary, fontSize: 12 }}>
            比較する発表を選択（最大5件）
          </div>

          {/* 発表選択チェックボックス */}
          <div style={{ marginBottom: 12, maxHeight: 120, overflowY: 'auto' }}>
            <Space wrap size={[8, 8]}>
              {releasesData.releases.map((release) => {
                const isSelected = selectedReleases.includes(release.release_datetime)
                const colorIdx = selectedReleases.indexOf(release.release_datetime)

                return (
                  <Checkbox
                    key={release.release_datetime}
                    checked={isSelected}
                    onChange={(e) => handleCompareSelect(release.release_datetime, e.target.checked)}
                    disabled={!isSelected && selectedReleases.length >= 5}
                    style={{
                      padding: '4px 8px',
                      backgroundColor: isSelected ? `${OVERLAY_COLORS[colorIdx]}20` : undefined,
                      borderRadius: 4,
                      border: isSelected ? `1px solid ${OVERLAY_COLORS[colorIdx]}` : '1px solid transparent',
                    }}
                  >
                    <span style={{ color: isSelected ? OVERLAY_COLORS[colorIdx] : undefined }}>
                      {formatReleaseShort(release)}
                    </span>
                  </Checkbox>
                )
              })}
            </Space>
          </div>

          {/* 選択された発表の詳細情報 */}
          {selectedReleases.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                gap: 8,
                padding: 8,
                backgroundColor: 'rgba(15, 23, 42, 0.5)',
                borderRadius: 6,
              }}
            >
              {selectedReleases.map((datetime, idx) => {
                const release = getSelectedReleaseInfo(datetime)
                if (!release) return null

                const surprise = release.surprise
                const surpriseColor = surprise != null
                  ? surprise > 0 ? '#22c55e' : surprise < 0 ? '#ef4444' : DARK_THEME.textSecondary
                  : DARK_THEME.textSecondary

                return (
                  <div
                    key={datetime}
                    style={{
                      padding: '6px 10px',
                      borderLeft: `3px solid ${OVERLAY_COLORS[idx]}`,
                      backgroundColor: 'rgba(30, 41, 59, 0.5)',
                      borderRadius: '0 4px 4px 0',
                    }}
                  >
                    <div style={{ fontSize: 11, color: OVERLAY_COLORS[idx], fontWeight: 'bold', marginBottom: 4 }}>
                      {formatReleaseShort(release)}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px', fontSize: 11 }}>
                      <span style={{ color: DARK_THEME.textSecondary }}>結果</span>
                      <span style={{ color: '#f1f5f9', textAlign: 'right' }}>
                        {release.actual?.toFixed(1) ?? '-'}
                      </span>
                      <span style={{ color: DARK_THEME.textSecondary }}>予想</span>
                      <span style={{ color: '#f1f5f9', textAlign: 'right' }}>
                        {release.estimate?.toFixed(1) ?? '-'}
                      </span>
                      <span style={{ color: DARK_THEME.textSecondary }}>差</span>
                      <span style={{ color: surpriseColor, textAlign: 'right' }}>
                        {surprise != null ? `${surprise > 0 ? '+' : ''}${surprise.toFixed(1)}` : '-'}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* チャート */}
      <div style={{ position: 'relative', minHeight: 400 }}>
        {isLoading && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'rgba(30, 41, 59, 0.8)',
              borderRadius: 8,
              zIndex: 10,
            }}
          >
            <Spin size="large" />
          </div>
        )}

        {mode === 'single' ? (
          singleChartData?.data?.length ? (
            // 1分足はローソク足、5分足はラインチャート
            interval === '1m' ? (
              <CandlestickChart
                data={singleChartData.data}
                height={400}
                releaseIndex={singleChartData.release_index}
                interval={interval}
              />
            ) : (
              <LineChart
                data={singleChartData.data}
                height={400}
                releaseIndex={singleChartData.release_index}
              />
            )
          ) : !isLoading ? (
            <Empty description="データがありません" style={{ height: 400, display: 'flex', flexDirection: 'column', justifyContent: 'center' }} />
          ) : null
        ) : (
          mergedCompareData.length ? (
            <ResponsiveContainer width="100%" height={400}>
              <ComposedChart
                data={mergedCompareData}
                margin={{ top: 16, right: 16, bottom: 60, left: 16 }}
                style={{ backgroundColor: DARK_THEME.chartBg }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />
                <XAxis
                  dataKey="minutes"
                  type="number"
                  domain={interval === '1m' ? [-60, 60] : [-1440, 1440]}
                  ticks={xAxisTicks}
                  axisLine={{ stroke: DARK_THEME.axisLine }}
                  tickLine={{ stroke: DARK_THEME.axisLine }}
                  tick={{ fill: DARK_THEME.textSecondary, fontSize: 10 }}
                  tickFormatter={(v: number) => formatMinutesToTime(v)}
                />
                <YAxis
                  axisLine={{ stroke: DARK_THEME.axisLine }}
                  tickLine={{ stroke: DARK_THEME.axisLine }}
                  tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
                  tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                  label={{ value: '変化率', angle: -90, position: 'insideLeft', fill: DARK_THEME.textSecondary }}
                />
                <RechartsTooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null
                    return (
                      <div
                        style={{
                          backgroundColor: DARK_THEME.tooltipBg,
                          border: `1px solid ${DARK_THEME.tooltipBorder}`,
                          borderRadius: 8,
                          padding: '12px 16px',
                        }}
                      >
                        <div style={{ marginBottom: 8, color: '#f1f5f9', fontWeight: 'bold' }}>
                          {formatMinutesToTime(Number(label))}
                        </div>
                        {payload.map((item, idx) => (
                          <div key={idx} style={{ color: item.color, fontSize: 12 }}>
                            {compareData?.series[idx]?.label}: {Number(item.value) >= 0 ? '+' : ''}{Number(item.value).toFixed(3)}%
                          </div>
                        ))}
                      </div>
                    )
                  }}
                />
                <Legend
                  verticalAlign="bottom"
                  wrapperStyle={{ paddingTop: 20 }}
                />
                {/* 発表タイミングの縦線（黄色） */}
                <ReferenceLine
                  x={0}
                  stroke={DARK_THEME.releaseMarker}
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  label={{
                    value: '発表',
                    position: 'top',
                    fill: DARK_THEME.releaseMarker,
                    fontSize: 12,
                  }}
                />
                <ReferenceLine y={0} stroke={DARK_THEME.axisLine} strokeWidth={1} />

                {compareData?.series?.map((series, idx) => (
                  <Line
                    key={series.release_datetime}
                    type="monotone"
                    dataKey={`series_${idx}`}
                    stroke={OVERLAY_COLORS[idx]}
                    strokeWidth={2}
                    dot={false}
                    name={series.label}
                    connectNulls
                    isAnimationActive={false}
                  />
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          ) : !isLoading && selectedReleases.length === 0 ? (
            <Empty description="比較する発表を選択してください" style={{ height: 400, display: 'flex', flexDirection: 'column', justifyContent: 'center' }} />
          ) : !isLoading ? (
            <Empty description="データがありません" style={{ height: 400, display: 'flex', flexDirection: 'column', justifyContent: 'center' }} />
          ) : null
        )}
      </div>
    </ChartContainer>
  )
}
