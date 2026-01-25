/**
 * 春闘チャートコンポーネント（日本）
 *
 * データソース: 連合（日本労働組合総連合会）
 *
 * 表示:
 * - 春闘賃上げ率（加重平均）と組合員数賃上げ率（単純平均）の経年推移
 * - プレスリリース（PDF選択・プレビュー表示）
 *
 * 発表スケジュール:
 * - 不定期（2〜4月、計7回の速報発表）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip, Select, Modal, Typography } from 'antd'
import { AreaChartOutlined, CalendarOutlined, FilePdfOutlined, ExpandOutlined, LinkOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'
import type { JapanShuntouData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import {
  LATEST_VALUE_BOX_STYLE,
  TEXT_COLORS,
} from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

const { Text } = Typography

// =============================================================================
// 型定義
// =============================================================================

interface ShuntouChartProps {
  data: JapanShuntouData | null
}

interface ChartDataPoint {
  date: string
  wageIncrease: number | null
  unionMember: number | null
}

interface PressRelease {
  number: number
  url: string
  year: number
  title: string
}

// グラフの色
const COLORS = {
  wageIncrease: '#1890ff',  // 青：賃上げ率（加重平均）
  unionMember: '#52c41a',   // 緑：組合員数賃上げ率
  positive: '#52c41a',
  negative: '#f5222d',
}

// =============================================================================
// ヘルパー関数
// =============================================================================

// 期間フィルタリング
const filterByPeriod = (
  data: ChartDataPoint[],
  period: PeriodValue,
  defaultStartYear: number = 2000
): ChartDataPoint[] => {
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

// 日付フォーマット関数（年度）
const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return `${date.getFullYear()}年`
}

// 値フォーマット関数
const formatValue = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '-'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

// 次回発表日時フォーマット関数
const formatNextRelease = (nextRelease: JapanShuntouData['next_release']): string | null => {
  if (!nextRelease) return null

  if (nextRelease.date) {
    const dt = new Date(nextRelease.date)
    const month = dt.getMonth() + 1
    const day = dt.getDate()

    if (nextRelease.label) {
      return `${month}/${day} (${nextRelease.label})`
    }
    return `${month}/${day}`
  }

  return null
}

// =============================================================================
// プレスリリースコンポーネント（プルダウン + PDFプレビュー）
// =============================================================================

function PressReleaseViewer({ pressReleases }: { pressReleases: PressRelease[] }) {
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // 最新版を初期選択（年度降順、回数降順でソート）
  const sortedReleases = useMemo(() => {
    return [...pressReleases].sort((a, b) => {
      if (a.year !== b.year) return b.year - a.year
      return b.number - a.number
    })
  }, [pressReleases])

  // 最新のプレスリリースを初期選択
  const latestRelease = sortedReleases[0]
  const currentUrl = selectedUrl ?? latestRelease?.url ?? null

  if (!pressReleases || pressReleases.length === 0) {
    return (
      <div style={{ marginTop: 16, padding: 16, background: '#fafafa', borderRadius: 8, textAlign: 'center' }}>
        <FilePdfOutlined style={{ fontSize: 24, color: '#999', marginBottom: 8 }} />
        <div>
          <Text type="secondary">プレスリリースはまだ公開されていません</Text>
        </div>
      </div>
    )
  }

  // プルダウンオプションを作成
  const selectOptions = sortedReleases.map((release) => ({
    value: release.url,
    label: `${release.year}年 第${release.number}回回答集計結果`,
  }))

  const currentRelease = sortedReleases.find(r => r.url === currentUrl)

  return (
    <div style={{ marginTop: 8 }}>
      {/* プルダウン選択 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        <FilePdfOutlined style={{ fontSize: 16, color: '#1890ff' }} />
        <Text strong>プレスリリース:</Text>
        <Select
          value={currentUrl}
          onChange={setSelectedUrl}
          options={selectOptions}
          style={{ minWidth: 280 }}
          placeholder="プレスリリースを選択"
        />
        {currentUrl && (
          <Tooltip title="PDFを新しいタブで開く">
            <Button
              type="link"
              icon={<LinkOutlined />}
              href={currentUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              PDF
            </Button>
          </Tooltip>
        )}
      </div>

      {/* PDFプレビュー（1ページ目） */}
      {currentUrl && (
        <div
          style={{
            position: 'relative',
            border: '1px solid #d9d9d9',
            borderRadius: 8,
            overflow: 'hidden',
            background: '#f5f5f5',
          }}
        >
          {/* PDFをiframeで表示 */}
          <div
            style={{
              width: '100%',
              height: 500,
              cursor: 'pointer',
            }}
            onClick={() => setIsModalOpen(true)}
          >
            <iframe
              src={`${currentUrl}#page=1&toolbar=0&view=FitH,300`}
              style={{
                width: '100%',
                height: '100%',
                border: 'none',
                pointerEvents: 'none',  // クリックはdivで受ける
              }}
              title={currentRelease?.title ?? 'プレスリリース'}
            />
          </div>

          {/* 拡大ボタン */}
          <Tooltip title="クリックで拡大表示">
            <Button
              type="primary"
              icon={<ExpandOutlined />}
              style={{
                position: 'absolute',
                top: 8,
                right: 8,
                opacity: 0.9,
              }}
              onClick={() => setIsModalOpen(true)}
            >
              拡大
            </Button>
          </Tooltip>
        </div>
      )}

      {/* 拡大表示モーダル */}
      <Modal
        title={currentRelease ? `${currentRelease.year}年 第${currentRelease.number}回回答集計結果` : 'プレスリリース'}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={[
          <Button key="link" type="link" href={currentUrl ?? ''} target="_blank" icon={<LinkOutlined />}>
            PDFを開く
          </Button>,
          <Button key="close" onClick={() => setIsModalOpen(false)}>
            閉じる
          </Button>,
        ]}
        width="52%"
        style={{ top: 20 }}
        styles={{ body: { height: 'calc(100vh - 120px)', padding: 0 } }}
      >
        {currentUrl && (
          <iframe
            src={currentUrl}
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
            }}
            title={currentRelease?.title ?? 'プレスリリース'}
          />
        )}
      </Modal>
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ShuntouChart({ data }: ShuntouChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')

  // チャートデータに変換（2系列をマージ）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const wageData = data.wage_increase?.data ?? []
    const unionData = data.union_member?.data ?? []

    // 全ての日付を収集
    const dateSet = new Set<string>()
    wageData.forEach(d => dateSet.add(d.date))
    unionData.forEach(d => dateSet.add(d.date))

    // 日付でマージ
    const dates = Array.from(dateSet).sort()
    const wageMap = new Map(wageData.map(d => [d.date, d.value]))
    const unionMap = new Map(unionData.map(d => [d.date, d.value]))

    return dates.map(date => ({
      date,
      wageIncrease: wageMap.get(date) ?? null,
      unionMember: unionMap.get(date) ?? null,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2000)
  }, [chartData, currentPeriod])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestWageIncrease = data?.wage_increase?.latest
  const latestUnionMember = data?.union_member?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="春闘" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="春闘" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="shuntou-chart">
      <ChartContainer
        title="春闘賃上げ率"
        showPeriodSelector={false}
        dataSource="連合（日本労働組合総連合会）"
        sourceUrl="https://www.jtuc-rengo.or.jp/activity/roudou/shuntou/"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {/* 年度 */}
            {latestWageIncrease?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDate(latestWageIncrease.date)}
              </span>
            )}
            {/* 賃上げ率（加重平均） */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: COLORS.wageIncrease,
                display: 'inline-block',
              }} />
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>賃上げ率:</span>
              <span style={{
                fontSize: 20,
                fontWeight: 'bold',
                color: (latestWageIncrease?.value ?? 0) >= 0 ? COLORS.positive : COLORS.negative
              }}>
                {formatValue(latestWageIncrease?.value)}
              </span>
            </div>
            {/* 組合員数賃上げ率（単純平均） */}
            {latestUnionMember?.value !== undefined && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  background: COLORS.unionMember,
                  display: 'inline-block',
                }} />
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>組合員数:</span>
                <span style={{
                  fontSize: 16,
                  fontWeight: 'bold',
                  color: (latestUnionMember?.value ?? 0) >= 0 ? COLORS.positive : COLORS.negative
                }}>
                  {formatValue(latestUnionMember?.value)}
                </span>
              </div>
            )}
          </div>

          {/* 右側: 次回発表 */}
          {data?.next_release && formatNextRelease(data.next_release) && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: TEXT_COLORS.secondary,
            }}>
              <CalendarOutlined />
              <span>次回発表: {formatNextRelease(data.next_release)}</span>
              {data.next_release.estimated && (
                <span style={{ color: TEXT_COLORS.tertiary }}></span>
              )}
            </div>
          )}
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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=jp_shuntou', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示（2系列の線グラフ） */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'wageIncrease', color: COLORS.wageIncrease, name: '賃上げ率', hide: false },
                      { dataKey: 'unionMember', color: COLORS.unionMember, name: '中小組合賃上げ率', hide: false },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                    showZeroLine={true}
                  />

                  {/* プレスリリースビューア */}
                  <PressReleaseViewer pressReleases={data?.press_releases ?? []} />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="jp_shuntou" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
