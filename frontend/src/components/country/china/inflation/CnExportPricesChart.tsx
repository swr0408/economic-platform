/**
 * 中国 輸出物価指数（Chinese Export Prices）チャート
 *
 * 系列: index（前年同月=100）のみ表示
 * グラフ: 折れ線
 *
 * データソース: 中國海關總署（GACC）
 *   http://gdfs.customs.gov.cn/customs/syx/index.html
 * 更新方法: backend/data/manual_update/monthly/china/中国輸出物価.csv を更新後、
 *   import_cn_export_prices_csv.py を実行
 *
 * FMPマッピングなし → マーケットインパクトタブ・次回発表日は表示しない
 */
import { useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { CnExportPricesData } from '../../../../hooks/useDashboardData'

interface Props {
  data: CnExportPricesData | null
}

interface ChartDataPoint {
  date: string
  index: number | null
}

const COLOR_PRIMARY = '#C53030'

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

export default function CnExportPricesChart({ data }: Props) {
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('index', {
    index: 10,
  })

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.data) return []
    return data.data.map(d => ({
      date: d.date,
      index: d.index,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="輸出物価指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="輸出物価指数" showPeriodSelector={false} showDataSource={false} handbookId="cn-export-prices">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="export-prices">
      <ChartContainer
        title="輸出物価指数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中國海關總署 (GACC)"
        sourceUrl="http://gdfs.customs.gov.cn/customs/syx/index.html"
        handbookId="cn-export-prices"
      >
        <SimpleLatestValueBox
          label="輸出物価指数（前年同月=100）"
          value={latest?.index ?? null}
          date={latest?.date}
          unit=""
          decimals={1}
          valueColor={COLOR_PRIMARY}
          dateFormatter={formatDateFull}
        />

        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=cn_export_prices', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <PeriodSelector
          onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
          selectedPeriod={currentPeriod}
        />

        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'index', color: COLOR_PRIMARY, name: '輸出物価指数' },
          ]}
          yAxisFormatter={(v) => v.toFixed(1)}
          yDomain={['dataMin - 2', 'dataMax + 2']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v) => v.toFixed(1)}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
