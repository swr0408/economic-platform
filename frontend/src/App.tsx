import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MainLayout from './components/layout/MainLayout'
import HomePage from './pages/HomePage'
import SeasonalityPage from './pages/SeasonalityPage'
import CountryDataPage from './pages/CountryDataPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<HomePage />} />
          <Route path="seasonality" element={<SeasonalityPage />} />
          <Route path="country-data" element={<CountryDataPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
