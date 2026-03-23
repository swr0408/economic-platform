import TsmcRevenueChart from './TsmcRevenueChart'
import LazyChart from '../../common/LazyChart'

export default function TwSemiconductorCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="tsmc-revenue"><TsmcRevenueChart /></LazyChart>
    </div>
  )
}
