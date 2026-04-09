import { useEffect, useRef, useState, memo } from 'react'
import ChartContainer from '../../common/ChartContainer'

const HEATMAP_HEIGHT = 650

function Nasdaq100HeatmapChart() {
  const container = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState<number>(0)

  // コンテナ幅を計測
  useEffect(() => {
    if (!container.current) return
    const el = container.current
    const update = () => setWidth(el.clientWidth)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // 幅が決まったらスクリプトを注入
  useEffect(() => {
    if (!container.current || width === 0) return

    container.current.innerHTML = ''

    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js'
    script.type = 'text/javascript'
    script.async = true
    script.innerHTML = JSON.stringify({
      dataSource: 'NASDAQ100',
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
  }, [width])

  return (
    <ChartContainer
      title="NASDAQ 100 ヒートマップ"
      dataSource="TradingView"
      sourceUrl="https://jp.tradingview.com/heatmap/stock/"
      showPeriodSelector={false}
    >
      <div
        className="tradingview-widget-container"
        ref={container}
        style={{ height: HEATMAP_HEIGHT, width: '100%' }}
      />
    </ChartContainer>
  )
}

export default memo(Nasdaq100HeatmapChart)
