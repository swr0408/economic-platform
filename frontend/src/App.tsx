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
import SmcHandbookPage from './pages/SmcHandbookPage'
import HeadlinesInboxPage from './pages/HeadlinesInboxPage'
import HeadlinesSavedPage from './pages/HeadlinesSavedPage'
import HeadlinesAdminPage from './pages/HeadlinesAdminPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import TermsPage from './pages/TermsPage'
import PrivacyPolicyPage from './pages/PrivacyPolicyPage'
import ChangePasswordPage from './pages/ChangePasswordPage'
import AdminUsersPage from './pages/AdminUsersPage'
import AdminVisibilityPage from './pages/AdminVisibilityPage'
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
            <Route path="/terms" element={<TermsPage />} />
            <Route path="/privacy" element={<PrivacyPolicyPage />} />

            {/*
              EconAlpha は会員制サイト。MainLayout 配下は全てログイン必須。
              未ログインでアクセスすると ProtectedRoute が /login へリダイレクトする。
              public visibility は「未認証公開」ではなく「ログイン済み一般ユーザ向け公開」を意味する。
            */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
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
              <Route path="smc" element={<SmcHandbookPage />} />

              {/* special/master 限定: ヘッドライン inbox */}
              <Route
                path="inbox"
                element={
                  <ProtectedRoute allowedRoles={['special', 'master']}>
                    <HeadlinesInboxPage />
                  </ProtectedRoute>
                }
              />
              {/* master 限定: 保存済みヘッドライン管理 */}
              <Route
                path="saved"
                element={
                  <ProtectedRoute allowedRoles={['master']}>
                    <HeadlinesSavedPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="saved/:categoryId"
                element={
                  <ProtectedRoute allowedRoles={['master']}>
                    <HeadlinesSavedPage />
                  </ProtectedRoute>
                }
              />

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

              {/* master 限定: 可視性管理 */}
              <Route
                path="admin/visibility"
                element={
                  <ProtectedRoute allowedRoles={['master']}>
                    <AdminVisibilityPage />
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
