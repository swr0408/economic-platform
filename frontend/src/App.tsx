import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MainLayout from './components/layout/MainLayout'
import HomePage from './pages/HomePage'
import SeasonalityPage from './pages/SeasonalityPage'
import SymbolDetailPage from './pages/SymbolDetailPage'
import CountryDataIndex from './pages/CountryDataIndex'
import CountryDetail from './pages/CountryDetail'
import CountryDataCategory from './pages/CountryDataCategory'
import MarketDataIndex from './pages/MarketDataIndex'
import MarketDataCategory from './pages/MarketDataCategory'
import EarningsIndex from './pages/EarningsIndex'
import EarningsCategory from './pages/EarningsCategory'
import ComparePage from './pages/ComparePage'
import DataHandbookPage from './pages/DataHandbookPage'
import { HandbookProvider } from './contexts/HandbookContext'

function App() {
  return (
    <HandbookProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<HomePage />} />
            <Route path="seasonality" element={<SeasonalityPage />} />
            <Route path="seasonality/:symbol" element={<SymbolDetailPage />} />
            <Route path="country" element={<CountryDataIndex />} />
            <Route path="country/:countryCode" element={<CountryDetail />} />
            <Route path="country/:countryCode/:categoryCode" element={<CountryDataCategory />} />
            <Route path="markets" element={<MarketDataIndex />} />
            <Route path="markets/:categoryCode" element={<MarketDataCategory />} />
            <Route path="markets/:categoryCode/:subCategoryCode" element={<MarketDataCategory />} />
            <Route path="earnings" element={<EarningsIndex />} />
            <Route path="earnings/:categoryCode" element={<EarningsCategory />} />
            <Route path="earnings/:categoryCode/:countryCode" element={<EarningsCategory />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="handbook" element={<DataHandbookPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </HandbookProvider>
  )
}

export default App
