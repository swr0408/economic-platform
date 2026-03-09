/**
 * Japan Import/Export Price Index Chart Component
 * 輸入・輸出物価指数チャート
 *
 * データ項目:
 * - export_yen_yoy: 輸出物価指数（円ベース）前年同月比 (%)
 * - import_yen_yoy: 輸入物価指数（円ベース）前年同月比 (%)
 * - import_contract_yoy: 輸入物価指数（契約通貨ベース）前年同月比 (%)
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
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import {
  fetchImportExportPriceData,
  type ImportExportPriceResponse,
  type ImportExportPriceDataPoint,
} from '../../../../utils/japan/importExportPriceApi'

// =============================================================================
// 定数
// =============================================================================

// カラー設定
const COLORS = {
  export_yen: '#36a2eb',
  import_yen: '#ff6384',
  import_contract: '#4bc0c0',
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

export default function JapanImportExportPriceChart() {
  const [data, setData] = useState<ImportExportPriceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<number | 'default' | 'all'>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchImportExportPriceData()
        if (res.error) {
          setError(res.error)
        } else {
          setData(res)
        }
      } catch (err) {
        console.error('Error loading Import/Export Price data:', err)
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
      .filter((d: ImportExportPriceDataPoint) =>
        d.export_yen_yoy !== null || d.import_yen_yoy !== null || d.import_contract_yoy !== null
      )
      .map((d: ImportExportPriceDataPoint) => ({
        date: d.date,
        export_yen_yoy: d.export_yen_yoy,
        import_yen_yoy: d.import_yen_yoy,
        import_contract_yoy: d.import_contract_yoy,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2021,
  })

  const hasData = sortedData.length > 0

  // ローディング状態
  if (loading) {
    return <LoadingChart title="輸入・輸出物価指数（前年比）" />
  }

  // エラー状態
  if (error) {
    return (
      <ChartContainer title="輸入・輸出物価指数（前年比）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="輸入・輸出物価指数（前年比）" showPeriodSelector={false} showDataSource={false}>
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
    <div id="japan-import-export-price-chart">
      <ChartContainer
        title="輸入・輸出物価指数（前年比）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="日本銀行"
        sourceUrl="https://www.boj.or.jp/statistics/pi/cgpi_release/index.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '輸出物価（円ベース）',
              value: latest?.export_yen_yoy,
              color: COLORS.export_yen,
              format: 'percent',
            },
            {
              label: '輸入物価（円ベース）',
              value: latest?.import_yen_yoy,
              color: COLORS.import_yen,
              format: 'percent',
            },
            {
              label: '輸入物価（契約通貨）',
              value: latest?.import_contract_yoy,
              color: COLORS.import_contract,
              format: 'percent',
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
              onClick={() => window.open('/compare?s=japan_export_price_yoy&s=japan_import_price_yen_yoy&s=japan_import_price_contract_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'export_yen_yoy', color: COLORS.export_yen, name: '輸出物価（円ベース）', hide: hiddenSeries.has('export_yen_yoy') },
            { dataKey: 'import_yen_yoy', color: COLORS.import_yen, name: '輸入物価（円ベース）', hide: hiddenSeries.has('import_yen_yoy') },
            { dataKey: 'import_contract_yoy', color: COLORS.import_contract, name: '輸入物価（契約通貨）', hide: hiddenSeries.has('import_contract_yoy') },
          ]}
          yAxisFormatter={(v: number) => `${v}%`}
          yDomain={['dataMin - 1', 'dataMax + 1']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateLabelJP}
          tooltipValueFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
