import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MainLayout from './components/layout/MainLayout'
import HomePage from './pages/HomePage'
import SeasonalityPage from './pages/SeasonalityPage'
import SymbolDetailPage from './pages/SymbolDetailPage'
import CountryDataIndex from './pages/CountryDataIndex'
import CountryDetail from './pages/CountryDetail'
import CountryDataCategory from './pages/CountryDataCategory'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<HomePage />} />
          <Route path="seasonality" element={<SeasonalityPage />} />
          <Route path="seasonality/:symbol" element={<SymbolDetailPage />} />
          <Route path="country" element={<CountryDataIndex />} />
          <Route path="country/:countryCode" element={<CountryDetail />} />
          <Route path="country/:countryCode/:categoryCode" element={<CountryDataCategory />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
