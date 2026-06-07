import { useEffect, useRef, useState, memo } from 'react'
import ChartContainer from '../../common/ChartContainer'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'

const HEATMAP_HEIGHT = 650

type HeatmapMode = 'sp500' | 'nasdaq100' | 'dow'

const HEATMAP_OPTIONS = [
  { mode: 'sp500' as HeatmapMode, label: 'S&P 500' },
  { mode: 'nasdaq100' as HeatmapMode, label: 'NASDAQ 100' },
  { mode: 'dow' as HeatmapMode, label: 'ダウ平均' },
]

const DATA_SOURCE_MAP: Record<HeatmapMode, string> = {
  sp500: 'SPX500',
  nasdaq100: 'NASDAQ100',
  dow: 'DJDJI',
}

function UsEquitiesHeatmapChart() {
  const container = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState<number>(0)
  const [mode, setMode] = useState<HeatmapMode>('sp500')

  useEffect(() => {
    if (!container.current) return
    const el = container.current
    const update = () => setWidth(el.clientWidth)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!container.current || width === 0) return

    container.current.innerHTML = ''

    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js'
    script.type = 'text/javascript'
    script.async = true
    script.innerHTML = JSON.stringify({
      dataSource: DATA_SOURCE_MAP[mode],
      blockSize: 'market_cap_basic',
      blockColor: 'change',
      grouping: 'sector',
      locale: 'ja',
      symbolUrl: '',
      colorTheme: 'dark',
      exchanges: [],
      hasTopBar: false,
      isDataSetEnabled: false,
      isZoomEnabled: true,
      hasSymbolTooltip: true,
      isMonoSize: false,
      width,
      height: HEATMAP_HEIGHT,
    })

    container.current.appendChild(script)

    return () => {
      if (container.current) {
        container.current.innerHTML = ''
      }
    }
  }, [width, mode])

  return (
    <ChartContainer
      title="米国株 ヒートマップ"
      dataSource="TradingView"
      sourceUrl="https://jp.tradingview.com/heatmap/stock/"
      showPeriodSelector={false}
    >
      <ViewModeButtonGroup
        options={HEATMAP_OPTIONS}
        currentMode={mode}
        onChange={(m) => setMode(m as HeatmapMode)}
      />
      <div
        className="tradingview-widget-container"
        ref={container}
        style={{ height: HEATMAP_HEIGHT, width: '100%' }}
      />
    </ChartContainer>
  )
}

export default memo(UsEquitiesHeatmapChart)
