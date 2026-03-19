import { useState } from 'react'
import ChartContainer from '../../common/ChartContainer'
import { ViewModeButtonGroup } from '../../country/usa/common/ChartComponents'

type ForexIvMode = 'major' | 'cross_jpy' | 'cross_g10'

const WIDGET_OPTIONS = [
  { mode: 'major' as ForexIvMode, label: 'メジャー' },
  { mode: 'cross_jpy' as ForexIvMode, label: 'クロス円' },
  { mode: 'cross_g10' as ForexIvMode, label: 'クロスG10' },
]

const WIDGET_URLS: Record<ForexIvMode, string> = {
  major: 'https://widget2.sentryd.com/widget/#/3f05aebc-97bd-4c05-883d-facf9311a495',
  cross_jpy: 'https://widget2.sentryd.com/widget/#/6884f7c8-9da7-48bf-b364-8d53cf29f67e',
  cross_g10: 'https://widget2.sentryd.com/widget/#/7176d14e-0df6-4dfa-8b89-3b0fb7b225be',
}

export default function ForexIvChart() {
  const [mode, setMode] = useState<ForexIvMode>('major')

  return (
    <ChartContainer
      title="為替オプション IV"
      dataSource="Sentry Derivatives"
      sourceUrl="https://sentryderivatives.com/"
      showPeriodSelector={false}
    >
      <div style={{ marginBottom: 8 }}>
        <ViewModeButtonGroup
          options={WIDGET_OPTIONS}
          currentMode={mode}
          onChange={(m) => setMode(m as ForexIvMode)}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <iframe
          key={mode}
          width="1100"
          height="711"
          src={WIDGET_URLS[mode]}
          title={`Forex IV - ${WIDGET_OPTIONS.find(o => o.mode === mode)?.label}`}
          style={{ border: 'none', borderRadius: 8 }}
        />
      </div>
    </ChartContainer>
  )
}
