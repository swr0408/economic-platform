/**
 * 自動車販売台数チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { TotalVehicleSalesData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  formatDateLabelJP,
  createUnitFormatter,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  SimpleLatestValueBox,
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTable } from '../common/MonthlyTable'


// =============================================================================
// 型定義
// =============================================================================

interface TotalVehicleSalesChartProps {
  data: TotalVehicleSalesData | null
}

// 指標種別
type DataKind = 'value' | 'yoy' | 'mom'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'value', label: '原数値' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// カラー設定
const COLORS = {
  value: CHART_COLORS.purple,
  yoy: CHART_COLORS.positive,
  mom: CHART_COLORS.primary,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function TotalVehicleSalesChart({ data }: TotalVehicleSalesChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // 指標種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 'default',
    yoy: 'default',
    mom: 3,
  })

  // データを日付昇順にソート
  const chartData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // 月別テーブルデータ
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom, 10)

  const hasData = chartData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="自動車販売台数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer
        title="自動車販売台数"
        showPeriodSelector={false}
        showDataSource={false}
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  // サブラベル・サブバリューの取得
  const getSubInfo = () => {
    if (dataKind === 'yoy') {
      return { label: '前年比', value: latest?.yoy }
    }
    if (dataKind === 'mom') {
      return { label: '前月比', value: latest?.mom }
    }
    return { label: undefined, value: undefined }
  }

  const subInfo = getSubInfo()

  return (
    <div id="total-vehicle-sales">
      <ChartContainer
        title="自動車販売台数"
        showPeriodSelector={false}
        dataSource="U.S. Bureau of Economic Analysis"
        sourceUrl="https://fred.stlouisfed.org/series/TOTALSA"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="最新値"
          value={latest?.value}
          valueColor={COLORS.value}
          subLabel={subInfo.label}
          subValue={subInfo.value}
          subValueColor={dataKind === 'yoy' ? COLORS.yoy : COLORS.mom}
          date={latest?.date}
          nextRelease={data.next_release}
          format="number"
          unit="M"
        />

        {/* 上段: 指標種別 + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <ViewModeButtonGroup
            options={DATA_KIND_OPTIONS}
            currentMode={dataKind}
            onChange={setDataKind}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=total_vehicle_sales', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 下段: 表示形式（前月比のときのみ） */}
        {dataKind === 'mom' && (
          <div style={{ marginBottom: 8 }}>
            <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
          </div>
        )}

        {/* 原数値グラフ */}
        {dataKind === 'value' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'value', color: COLORS.value, name: '自動車販売台数' },
              ]}
              yAxisFormatter={(v) => `${v}M`}
              yDomain={['dataMin - 2', 'dataMax + 2']}
              tooltipLabelFormatter={formatDateLabelJP}
              tooltipFormatter={createUnitFormatter('M', 2)}
              showZeroLine={false}
              showLegend={false}
            />
          </>
        )}

        {/* 前年比グラフ */}
        {dataKind === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'yoy', color: COLORS.yoy, name: '前年比' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 5', 'dataMax + 5']}
              tooltipLabelFormatter={formatDateLabelJP}
              showLegend={false}
            />
          </>
        )}

        {/* 前月比ヒートマップ */}
        {dataKind === 'mom' && displayMode === 'heatmap' && (
          <MonthlyTable
            data={momTableData}
            thresholdType="vehicle"
            showLegend={true}
          />
        )}

        {/* 前月比チャート */}
        {dataKind === 'mom' && displayMode === 'chart' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardBarChart
              data={filteredData}
              bars={[
                { dataKey: 'mom', color: COLORS.mom, name: '前月比' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 3', 'dataMax + 3']}
              tooltipLabelFormatter={formatDateLabelJP}
            />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
