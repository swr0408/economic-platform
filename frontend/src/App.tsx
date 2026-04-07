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
import HeadlinesInboxPage from './pages/HeadlinesInboxPage'
import HeadlinesSavedPage from './pages/HeadlinesSavedPage'
import HeadlinesAdminPage from './pages/HeadlinesAdminPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ChangePasswordPage from './pages/ChangePasswordPage'
import AdminUsersPage from './pages/AdminUsersPage'
import ProtectedRoute from './components/auth/ProtectedRoute'
import { HandbookProvider } from './contexts/HandbookContext'
import { AuthProvider } from './contexts/AuthContext'

function App() {
  return (
    <AuthProvider>
      <HandbookProvider>
        <BrowserRouter>
          <Routes>
            {/* 認証画面 (MainLayout の外に配置) */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

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
              <Route path="inbox" element={<HeadlinesInboxPage />} />
              <Route path="saved" element={<HeadlinesSavedPage />} />
              <Route path="saved/:categoryId" element={<HeadlinesSavedPage />} />

              {/* 認証必須: 自分のパスワード変更 */}
              <Route
                path="account/password"
                element={
                  <ProtectedRoute>
                    <ChangePasswordPage />
                  </ProtectedRoute>
                }
              />

              {/* master 限定: ヘッドライン管理 */}
              <Route
                path="admin/headlines"
                element={
                  <ProtectedRoute allowedRoles={['master']}>
                    <HeadlinesAdminPage />
                  </ProtectedRoute>
                }
              />

              {/* master 限定: ユーザー管理 */}
              <Route
                path="admin/users"
                element={
                  <ProtectedRoute allowedRoles={['master']}>
                    <AdminUsersPage />
                  </ProtectedRoute>
                }
              />
            </Route>
          </Routes>
        </BrowserRouter>
      </HandbookProvider>
    </AuthProvider>
  )
}

export default App
