import ForexIvChart from './ForexIvChart'
import NyOptionCutChart from './NyOptionCutChart'
import LazyChart from '../../common/LazyChart'

export default function FxOptionsCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="forex-iv"><ForexIvChart /></LazyChart>
      <LazyChart id="ny-option-cut"><NyOptionCutChart /></LazyChart>
    </div>
  )
}
