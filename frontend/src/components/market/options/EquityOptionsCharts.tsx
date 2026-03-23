import Nikkei225OptionsChart from './Nikkei225OptionsChart'
import LazyChart from '../../common/LazyChart'

export default function EquityOptionsCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="nikkei225-options"><Nikkei225OptionsChart /></LazyChart>
    </div>
  )
}
