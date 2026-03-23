import UsNaturalGasStorageChart from './UsNaturalGasStorageChart'
import UsNaturalGasTradeChart from './UsNaturalGasTradeChart'
import LngExportsByRegionChart from './LngExportsByRegionChart'
import SteoNaturalGasChart from './SteoNaturalGasChart'
import EuNaturalGasStorageChart from './EuNaturalGasStorageChart'
import EuNaturalGasProductionChart from './EuNaturalGasProductionChart'
import NoaaHddCddChart from './NoaaHddCddChart'
import RoniChart from './RoniChart'
import CftcPositioningChart from '../cot/CftcPositioningChart'
import LazyChart from '../../common/LazyChart'

export default function NaturalGasCharts() {
  return (
    <div className="country-chart-stack">
      <LazyChart id="natural-gas-storage"><UsNaturalGasStorageChart /></LazyChart>
      <LazyChart id="natural-gas-trade"><UsNaturalGasTradeChart /></LazyChart>
      <LazyChart id="lng-exports-by-region"><LngExportsByRegionChart /></LazyChart>
      <LazyChart id="steo-natural-gas"><SteoNaturalGasChart /></LazyChart>
      <LazyChart id="noaa-hdd-cdd"><NoaaHddCddChart /></LazyChart>
      <LazyChart id="eu-natural-gas-storage"><EuNaturalGasStorageChart /></LazyChart>
      <LazyChart id="eu-natural-gas-production"><EuNaturalGasProductionChart /></LazyChart>
      <LazyChart id="roni"><RoniChart /></LazyChart>
      <LazyChart id="cot-natural-gas"><CftcPositioningChart asset="natural_gas" assetLabel="天然ガス" reportType="disagg" compareId="cftc_natural_gas" /></LazyChart>
    </div>
  )
}
