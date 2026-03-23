import React, { useEffect, useRef, memo } from 'react';
import { getTradingViewSymbol } from '../../utils/tradingViewSymbols';

interface TradingViewWidgetProps {
  symbol: string;
  height?: string | number;
  width?: string | number;
  /** チャートスタイル: "1"=Candles(デフォルト), "2"=Line, "3"=Area, "0"=Bar */
  chartStyle?: string;
  style?: React.CSSProperties;
}

function TradingViewWidget({
  symbol,
  height = 610,
  width = "100%",
  chartStyle = "1",
  style = {},
}: TradingViewWidgetProps) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    // 既存のスクリプトをクリア
    container.current.innerHTML = '';

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;

    const tradingViewSymbol = getTradingViewSymbol(symbol);

    script.innerHTML = JSON.stringify({
      "allow_symbol_change": true,
      "calendar": false,
      "details": false,
      "hide_side_toolbar": false,
      "hide_top_toolbar": false,
      "hide_legend": false,
      "hide_volume": true,
      "hotlist": false,
      "interval": "D",
      "locale": "ja",
      "save_image": true,
      "style": chartStyle,
      "symbol": tradingViewSymbol,
      "theme": "dark",
      "timezone": "Asia/Tokyo",
      "backgroundColor": "#0F0F0F",
      "gridColor": "rgba(242, 242, 242, 0.06)",
      "watchlist": [],
      "withdateranges": false,
      "compareSymbols": [],
      "studies": [],
      "autosize": true,
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, [symbol, chartStyle]);

  return (
    <div
      className="tradingview-widget-container"
      ref={container}
      style={{
        height: typeof height === 'number' ? `${height}px` : height,
        width: typeof width === 'number' ? `${width}px` : width,
        ...style,
      }}
    >
      <div className="tradingview-widget-container__widget" style={{ height: "100%", width: "100%" }} />
      <div className="tradingview-widget-copyright">
        <a
          href={`https://jp.tradingview.com/symbols/${getTradingViewSymbol(symbol).replace(':', '-')}/`}
          rel="noopener nofollow"
          target="_blank"
        >
          <span className="blue-text">Track all markets on TradingView</span>
        </a>
      </div>
    </div>
  );
}

export default memo(TradingViewWidget);
