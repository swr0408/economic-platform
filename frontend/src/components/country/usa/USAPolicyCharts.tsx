import PolicyRateChart from './monetary_policy/PolicyRateChart'
import TermPremiumChart from './monetary_policy/TermPremiumChart'
import CMEFedWatchChart from './monetary_policy/CMEFedWatchChart'
import FOMCProjectionsChart from './monetary_policy/FOMCProjectionsChart'

export default function USAPolicyCharts() {
  return (
    <div className="country-chart-stack">
      {/* Federal Funds Target Rate Chart */}
      <div id="policy-rate">
        <PolicyRateChart />
      </div>

      {/* CME FedWatch Tool */}
      <div id="fed-watch">
        <CMEFedWatchChart />
      </div>

      {/* ACM Term Premium Chart */}
      <div id="term-premium">
        <TermPremiumChart />
      </div>

      {/* FOMC Dot Plot */}
      <div id="dot-plot">
        <FOMCProjectionsChart />
      </div>
    </div>
  )
}
