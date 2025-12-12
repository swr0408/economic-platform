import React, { useEffect, useRef, memo } from 'react';
import { getTradingViewSymbol } from '../../utils/tradingViewSymbols';

interface TradingViewWidgetProps {
  symbol: string;
  height?: string | number;
  width?: string | number;
  theme?: 'light' | 'dark';
  interval?: string;
  timezone?: string;
  locale?: string;
  hideTopToolbar?: boolean;
  hideSideToolbar?: boolean;
  hideLegend?: boolean;
  hideVolume?: boolean;
  allowSymbolChange?: boolean;
  withDateRanges?: boolean; // 上部に日付レンジボタン群を表示
  range?: string; // 初期表示レンジ（例: '12M', '6M', '5D'）
  style?: React.CSSProperties;
}

function TradingViewWidget({
  symbol,
  height = "100%",
  width = "100%",
  theme = "light",
  interval = "60",
  timezone = "Asia/Tokyo",
  locale = "ja",
  hideTopToolbar = false,
  hideSideToolbar = true,
  hideLegend = false,
  hideVolume = true,
  allowSymbolChange = true,
  withDateRanges = true,
  range,
  style = {}
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
    
    const config: Record<string, unknown> = {
      "allow_symbol_change": allowSymbolChange,
      "calendar": false,
      "details": false,
      "hide_side_toolbar": hideSideToolbar,
      "hide_top_toolbar": hideTopToolbar,
      "hide_legend": hideLegend,
      "hide_volume": hideVolume,
      "hotlist": false,
      "interval": interval,
      "locale": locale,
      "save_image": true,
      "style": "1",
      "symbol": tradingViewSymbol,
      "theme": theme,
      "timezone": timezone,
      "backgroundColor": theme === "light" ? "#ffffff" : "#1E1E1E",
      "gridColor": theme === "light" ? "rgba(46, 46, 46, 0.06)" : "rgba(240, 240, 240, 0.06)",
      "watchlist": [],
      "withdateranges": withDateRanges,
      "compareSymbols": [],
      "studies": [],
      "autosize": true
    };
    if (range) {
      config["range"] = range;
    }

    script.innerHTML = JSON.stringify(config);

    container.current.appendChild(script);

    // クリーンアップ関数
    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, [symbol, theme, interval, timezone, locale, hideTopToolbar, hideSideToolbar, hideLegend, hideVolume, allowSymbolChange]);

  return (
    <div 
      className="tradingview-widget-container" 
      ref={container} 
      style={{ 
        height: typeof height === 'number' ? `${height}px` : height, 
        width: typeof width === 'number' ? `${width}px` : width,
        ...style
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
