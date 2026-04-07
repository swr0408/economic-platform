/**
 * マーケットインパクトタブ
 *
 * 経済指標発表時の価格変動チャートを表示
 * - 単独表示: 1つの発表を選択してチャート表示（1分足ローソク足、5分足ライン）
 * - オーバーレイ比較: 複数の発表を重ねて比較（発表時刻を0点として正規化）
 */
import { useState, useEffect, useMemo, useRef } from 'react'
import { Select, Spin, Segmented, Space, Tag, Empty, Checkbox, Tabs, Radio, Collapse, Alert } from 'antd'
import { LineChartOutlined, BarChartOutlined, LoadingOutlined, ReloadOutlined } from '@ant-design/icons'
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
import { withVisibility } from '../common/withVisibility'

// ダークテーマカラー
const DARK_THEME = {
  textSecondary: '#94a3b8',
  textPrimary: '#f1f5f9',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
  releaseMarker: '#fbbf24',
  bgSecondary: '#1e293b',
  bgTertiary: '#0f172a',
  borderLight: '#334155',
  accent: '#3b82f6',
}

// 銘柄カテゴリ定義
const SYMBOL_CATEGORIES = {
  forex: '為替',
  index: '株価指数',
  commodity: '商品',
  bond: '債券',
} as const

// サブカテゴリラベル
const SYMBOL_SUB_CATEGORY_LABELS: Record<string, string> = {
  // 為替
  major: 'メジャー通貨ペア',
  jpy_cross: 'クロス円',
  eur_cross: 'ユーロクロス',
  gbp_cross: 'ポンドクロス',
  other_cross: 'その他クロス',
  metal: '貴金属',
  // 株価指数
  us: '米国',
  asia: 'アジア',
  europe: '欧州',
  // 商品
  energy: 'エネルギー',
  agricultural: '農産物',
  // 債券
  government: '国債',
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
    return [-60, -45, -30, -15, 0, 15, 30, 45, 60]
  } else {
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
  event_name: string
}

interface ChartData {
  timestamp: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number
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

interface MarketImpactTabProps {
  indicatorId: string
}

// Dukascopy銘柄の型定義
interface DukascopySymbol {
  id: string
  name: string
  name_en: string
  category: string
  sub_category: string
}

// タイムアウト設定（秒）
const CHART_REQUEST_TIMEOUT = 30000  // 30秒
const RELEASES_REQUEST_TIMEOUT = 10000  // 10秒

function MarketImpactTab({ indicatorId }: MarketImpactTabProps) {
  const [mode, setMode] = useState<'single' | 'compare'>('single')
  const [selectedRelease, setSelectedRelease] = useState<string | null>(null)
  const [selectedReleases, setSelectedReleases] = useState<string[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState('usdjpy')
  const [interval, setInterval] = useState<'1m' | '5m'>('1m')
  const [symbolCategory, setSymbolCategory] = useState<string>('forex')
  const [chartError, setChartError] = useState<string | null>(null)

  // AbortController用のref
  const abortControllerRef = useRef<AbortController | null>(null)

  // Dukascopy銘柄一覧を取得（全カテゴリ）
  const { data: symbolsData } = useQuery({
    queryKey: ['market-impact-symbols'],
    queryFn: async () => {
      const res = await axios.get('/api/market-impact/symbols')
      return res.data as {
        symbols: DukascopySymbol[]
        categories: Record<string, string>
        sub_categories: Record<string, string>
        count: number
      }
    },
    staleTime: Infinity, // 静的データのため永続キャッシュ
  })

  // サブカテゴリ別にグループ化した銘柄リスト
  const symbolsBySubCategory = useMemo(() => {
    if (!symbolsData?.symbols) return {}

    const grouped: Record<string, DukascopySymbol[]> = {}
    symbolsData.symbols.forEach(symbol => {
      if (!grouped[symbol.sub_category]) {
        grouped[symbol.sub_category] = []
      }
      grouped[symbol.sub_category].push(symbol)
    })
    return grouped
  }, [symbolsData])

  // 現在のカテゴリに属するサブカテゴリ
  const currentCategorySubCategories = useMemo(() => {
    if (!symbolsData?.symbols) return []

    const subCats = new Set<string>()
    symbolsData.symbols
      .filter(s => s.category === symbolCategory)
      .forEach(s => subCats.add(s.sub_category))
    return Array.from(subCats)
  }, [symbolsData, symbolCategory])

  // 選択した銘柄の情報
  const selectedSymbolInfo = useMemo(() => {
    return symbolsData?.symbols?.find(s => s.id === selectedSymbol)
  }, [symbolsData, selectedSymbol])

  // コンポーネントアンマウント時にリクエストをキャンセル
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [])

  // 発表履歴を取得
  const { data: releasesData, isLoading: isLoadingReleases, error: releasesError, refetch: refetchReleases } = useQuery({
    queryKey: ['market-impact-releases', indicatorId],
    queryFn: async ({ signal }) => {
      const res = await axios.get(`/api/market-impact/releases/${indicatorId}`, {
        signal,
        timeout: RELEASES_REQUEST_TIMEOUT,
      })
      return res.data as { releases: Release[]; count: number }
    },
    staleTime: 24 * 60 * 60 * 1000, // 1日
    retry: 1, // リトライは1回のみ
  })

  // 最初の発表を選択
  useEffect(() => {
    if (releasesData?.releases?.length && !selectedRelease) {
      setSelectedRelease(releasesData.releases[0].release_datetime)
    }
  }, [releasesData, selectedRelease])

  // 選択中の発表の情報
  const selectedReleaseInfo = useMemo(() => {
    if (!selectedRelease || !releasesData?.releases) return null
    return releasesData.releases.find(r => r.release_datetime === selectedRelease)
  }, [selectedRelease, releasesData])

  // 単独表示用チャートデータを取得
  const { data: chartData, isLoading: isLoadingChart, isFetching: isFetchingChart, refetch: refetchChart } = useQuery({
    queryKey: ['market-impact-chart', selectedRelease, selectedSymbol, interval],
    queryFn: async ({ signal }) => {
      if (!selectedRelease) return null
      setChartError(null)

      try {
        const res = await axios.get('/api/market-impact/chart', {
          params: {
            release_datetime: selectedRelease,
            symbol_id: selectedSymbol,
            interval,
          },
          signal,
          timeout: CHART_REQUEST_TIMEOUT,
        })
        return res.data as {
          data: ChartData[]
          release_index: number | null
          count: number
        }
      } catch (error: any) {
        if (axios.isCancel(error)) {
          throw error // キャンセルの場合は再スロー
        }
        if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
          setChartError('データ取得がタイムアウトしました。再試行してください。')
        } else {
          setChartError('データ取得に失敗しました。')
        }
        throw error
      }
    },
    enabled: mode === 'single' && !!selectedRelease,
    staleTime: 24 * 60 * 60 * 1000, // 1日
    retry: 0, // チャートデータはリトライしない（ユーザーに再試行させる）
    refetchOnWindowFocus: false,
  })

  // 比較用データを取得
  const { data: compareData, isLoading: isLoadingCompare, isFetching: isFetchingCompare, refetch: refetchCompare } = useQuery({
    queryKey: ['market-impact-compare', selectedReleases, selectedSymbol, interval],
    queryFn: async ({ signal }) => {
      if (!selectedReleases.length) return null
      setChartError(null)

      try {
        const res = await axios.get('/api/market-impact/compare', {
          params: {
            release_datetimes: selectedReleases.join(','),
            symbol_id: selectedSymbol,
            interval,
          },
          signal,
          timeout: CHART_REQUEST_TIMEOUT,
        })
        return res.data as {
          series: CompareSeries[]
          count: number
        }
      } catch (error: any) {
        if (axios.isCancel(error)) {
          throw error
        }
        if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
          setChartError('データ取得がタイムアウトしました。再試行してください。')
        } else {
          setChartError('データ取得に失敗しました。')
        }
        throw error
      }
    },
    enabled: mode === 'compare' && selectedReleases.length > 0,
    staleTime: 24 * 60 * 60 * 1000, // 1日
    retry: 0,
    refetchOnWindowFocus: false,
  })

  // 比較用データをマージ
  const mergedCompareData = useMemo(() => {
    if (!compareData?.series?.length) return []

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

  // 発表日時のフォーマット
  const formatReleaseOption = (release: Release) => {
    const dt = new Date(release.release_datetime)
    const dateStr = dt.toLocaleDateString('ja-JP', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
    const timeStr = dt.toLocaleTimeString('ja-JP', {
      hour: '2-digit',
      minute: '2-digit',
    })
    return `${dateStr} ${timeStr}${release.period_label ? ` (${release.period_label})` : ''}`
  }

  // 発表日時の短縮フォーマット
  const formatReleaseShort = (release: Release) => {
    const dt = new Date(release.release_datetime)
    return dt.toLocaleDateString('ja-JP', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
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

  const isLoading = isLoadingReleases || (mode === 'single' ? (isLoadingChart || isFetchingChart) : (isLoadingCompare || isFetchingCompare))
  const xAxisTicks = generateXAxisTicks(interval)

  // リトライハンドラ
  const handleRetry = () => {
    setChartError(null)
    if (mode === 'single') {
      refetchChart()
    } else {
      refetchCompare()
    }
  }

  if (isLoadingReleases) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 48, gap: 16 }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
        <span style={{ color: DARK_THEME.textSecondary }}>発表履歴を読み込み中...</span>
      </div>
    )
  }

  if (releasesError) {
    return (
      <div style={{ padding: 24 }}>
        <Alert
          type="error"
          message="発表履歴の取得に失敗しました"
          description="ネットワーク接続を確認して再試行してください"
          action={
            <button
              onClick={() => refetchReleases()}
              style={{
                padding: '6px 16px',
                backgroundColor: DARK_THEME.accent,
                color: '#fff',
                border: 'none',
                borderRadius: 4,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <ReloadOutlined /> 再試行
            </button>
          }
        />
      </div>
    )
  }

  if (!releasesData?.releases?.length) {
    return (
      <Empty
        description="発表履歴がありません"
        style={{ padding: 48 }}
      />
    )
  }

  return (
    <div>
      {/* コントロール - 上部 */}
      <div style={{ marginBottom: 12 }}>
        <Space wrap size="middle">
          {/* モード切替 */}
          <Segmented
            value={mode}
            onChange={(v) => setMode(v as 'single' | 'compare')}
            options={[
              { value: 'single', label: '単独表示', icon: <BarChartOutlined /> },
              { value: 'compare', label: 'オーバーレイ比較', icon: <LineChartOutlined /> },
            ]}
          />

          {/* 単独表示: 発表日時選択 */}
          {mode === 'single' && (
            <Select
              value={selectedRelease}
              onChange={setSelectedRelease}
              style={{ width: 280 }}
              placeholder="発表日時を選択"
              options={releasesData.releases.map(r => ({
                value: r.release_datetime,
                label: formatReleaseOption(r),
              }))}
            />
          )}

          {/* 足種切替 */}
          <Segmented
            value={interval}
            onChange={(v) => setInterval(v as '1m' | '5m')}
            options={[
              { value: '1m', label: '1分足 (±1h)' },
              { value: '5m', label: '5分足 (±24h)' },
            ]}
          />

          {/* 選択中の銘柄表示 */}
          {selectedSymbolInfo && (
            <Tag color="blue" style={{ margin: 0, fontSize: 13 }}>
              {selectedSymbolInfo.name} ({selectedSymbolInfo.name_en})
            </Tag>
          )}
        </Space>
      </div>

      {/* 銘柄選択タブ */}
      <div
        style={{
          marginBottom: 16,
          padding: '8px 12px',
          backgroundColor: DARK_THEME.bgSecondary,
          borderRadius: 8,
          border: `1px solid ${DARK_THEME.borderLight}`,
        }}
      >
        <Tabs
          activeKey={symbolCategory}
          onChange={(key) => setSymbolCategory(key)}
          size="small"
          items={Object.entries(SYMBOL_CATEGORIES).map(([key, label]) => ({
            key,
            label,
            children: (
              <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                <Collapse
                  defaultActiveKey={currentCategorySubCategories.slice(0, 2)}
                  ghost
                  size="small"
                  items={currentCategorySubCategories.map(subCat => {
                    const symbols = symbolsBySubCategory[subCat] || []
                    return {
                      key: subCat,
                      label: (
                        <span style={{ fontSize: 12, color: DARK_THEME.textPrimary }}>
                          {SYMBOL_SUB_CATEGORY_LABELS[subCat] || subCat}
                          <span style={{ color: DARK_THEME.textSecondary, marginLeft: 4 }}>
                            ({symbols.length})
                          </span>
                        </span>
                      ),
                      children: (
                        <Radio.Group
                          value={selectedSymbol}
                          onChange={(e) => setSelectedSymbol(e.target.value)}
                          style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
                        >
                          {symbols.map(s => (
                            <Radio
                              key={s.id}
                              value={s.id}
                              style={{
                                padding: '4px 8px',
                                borderRadius: 4,
                                backgroundColor: selectedSymbol === s.id ? `${DARK_THEME.accent}20` : 'transparent',
                              }}
                            >
                              <span style={{ color: DARK_THEME.textPrimary, fontSize: 12 }}>
                                {s.name}
                              </span>
                              <span style={{ color: DARK_THEME.textSecondary, fontSize: 11, marginLeft: 6 }}>
                                {s.name_en}
                              </span>
                            </Radio>
                          ))}
                        </Radio.Group>
                      ),
                    }
                  })}
                />
              </div>
            ),
          }))}
        />
      </div>

      {/* 単独表示: 発表情報 */}
      {mode === 'single' && selectedReleaseInfo && (
        <div
          style={{
            marginBottom: 16,
            padding: '12px 16px',
            backgroundColor: 'rgba(30, 41, 59, 0.5)',
            borderRadius: 8,
            display: 'flex',
            flexWrap: 'wrap',
            gap: 16,
            alignItems: 'center',
          }}
        >
          <div>
            <span style={{ color: '#94a3b8', marginRight: 8 }}>結果:</span>
            <span style={{ fontSize: 18, fontWeight: 600, color: '#f1f5f9' }}>
              {selectedReleaseInfo.actual?.toFixed(1) ?? '-'}
            </span>
          </div>
          <div>
            <span style={{ color: '#94a3b8', marginRight: 8 }}>予想:</span>
            <span style={{ color: '#f1f5f9' }}>
              {selectedReleaseInfo.estimate?.toFixed(1) ?? '-'}
            </span>
          </div>
          <div>
            <span style={{ color: '#94a3b8', marginRight: 8 }}>前回:</span>
            <span style={{ color: '#f1f5f9' }}>
              {selectedReleaseInfo.previous?.toFixed(1) ?? '-'}
            </span>
          </div>
          {selectedReleaseInfo.surprise != null && (
            <Tag
              color={selectedReleaseInfo.surprise >= 0 ? 'green' : 'red'}
              style={{ margin: 0 }}
            >
              {selectedReleaseInfo.surprise >= 0 ? '+' : ''}
              {selectedReleaseInfo.surprise.toFixed(1)} サプライズ
            </Tag>
          )}
        </div>
      )}

      {/* 比較モード: 発表選択 */}
      {mode === 'compare' && (() => {
        // O(1)ルックアップ用のSetとMapを事前計算
        const selectedSet = new Set(selectedReleases)
        const selectedIndexMap = new Map(selectedReleases.map((dt, idx) => [dt, idx]))

        return (
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
                const isSelected = selectedSet.has(release.release_datetime)
                const colorIdx = selectedIndexMap.get(release.release_datetime) ?? -1

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
        )
      })()}

      {/* エラー表示 */}
      {chartError && (
        <Alert
          type="warning"
          message={chartError}
          action={
            <button
              onClick={handleRetry}
              style={{
                padding: '4px 12px',
                backgroundColor: DARK_THEME.accent,
                color: '#fff',
                border: 'none',
                borderRadius: 4,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 12,
              }}
            >
              <ReloadOutlined /> 再試行
            </button>
          }
          style={{ marginBottom: 12 }}
          closable
          onClose={() => setChartError(null)}
        />
      )}

      {/* チャート */}
      <div style={{ position: 'relative', minHeight: 400 }}>
        {isLoading && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'rgba(30, 41, 59, 0.9)',
              borderRadius: 8,
              zIndex: 10,
              gap: 12,
            }}
          >
            <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
            <span style={{ color: DARK_THEME.textSecondary, fontSize: 13 }}>
              チャートデータを取得中...
            </span>
            <span style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
              初回取得時は時間がかかることがあります
            </span>
          </div>
        )}

        {mode === 'single' ? (
          /* 単独表示 */
          chartData?.data?.length ? (
            interval === '1m' ? (
              <CandlestickChart
                data={chartData.data}
                height={400}
                releaseIndex={chartData.release_index}
                interval={interval}
              />
            ) : (
              <LineChart
                data={chartData.data}
                height={400}
                releaseIndex={chartData.release_index}
              />
            )
          ) : !isLoadingChart ? (
            <Empty
              description={
                <span>
                  データがありません<br />
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>
                    市場がクローズしている時間帯の可能性があります
                  </span>
                </span>
              }
              style={{
                height: 400,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                backgroundColor: '#1e293b',
                borderRadius: 8,
              }}
            />
          ) : null
        ) : (
          /* オーバーレイ比較 */
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
          ) : !isLoadingCompare && selectedReleases.length === 0 ? (
            <Empty
              description="比較する発表を選択してください"
              style={{
                height: 400,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                backgroundColor: '#1e293b',
                borderRadius: 8,
              }}
            />
          ) : !isLoadingCompare ? (
            <Empty
              description="データがありません"
              style={{
                height: 400,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                backgroundColor: '#1e293b',
                borderRadius: 8,
              }}
            />
          ) : null
        )}
      </div>
    </div>
  )
}

// special 限定 (一般ユーザには非表示)
export default withVisibility(MarketImpactTab, 'special')
