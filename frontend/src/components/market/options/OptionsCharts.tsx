import { Typography } from 'antd'
import Nikkei225OptionsChart from './Nikkei225OptionsChart'
import ForexIvChart from './ForexIvChart'
import NyOptionCutChart from './NyOptionCutChart'

const { Title } = Typography

export default function OptionsCharts() {
  return (
    <div className="country-chart-stack">
      <div id="equity-options">
        <Title level={4} style={{ color: '#f1f5f9', marginBottom: 16 }}>株式オプション</Title>
      </div>
      <div id="nikkei225-options">
        <Nikkei225OptionsChart />
      </div>

      <div id="fx-options" style={{ marginTop: 32 }}>
        <Title level={4} style={{ color: '#f1f5f9', marginBottom: 16 }}>為替オプション</Title>
      </div>
      <div id="forex-iv">
        <ForexIvChart />
      </div>
      <div id="ny-option-cut">
        <NyOptionCutChart />
      </div>
    </div>
  )
}
