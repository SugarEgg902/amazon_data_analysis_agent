import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import { MarketProvider } from './context/MarketContext'
import Overview from './pages/Overview'
import ProductList from './pages/ProductList'
import ProductDetail from './pages/ProductDetail'
import Compare from './pages/Compare'
import Trends from './pages/Trends'
import Anomalies from './pages/Anomalies'
import Reports from './pages/Reports'
import SalesAnalysis from './pages/SalesAnalysis'
import AmazonSearch from './pages/AmazonSearch'
import BrandDetail from './pages/BrandDetail'
import ModelRanking from './pages/ModelRanking'

const qc = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
})

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <MarketProvider>
        <BrowserRouter>
          <Layout>
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<Navigate to="/overview" replace />} />
                <Route path="/overview" element={<Overview />} />
                <Route path="/products" element={<ProductList />} />
                <Route path="/products/:asin" element={<ProductDetail />} />
                <Route path="/compare" element={<Compare />} />
                <Route path="/trends" element={<Trends />} />
                <Route path="/anomalies" element={<Anomalies />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/sales-analysis" element={<SalesAnalysis />} />
                <Route path="/search" element={<AmazonSearch />} />
                <Route path="/brands/:brand" element={<BrandDetail />} />
                <Route path="/brands/:brand/models/:type" element={<ModelRanking />} />
              </Routes>
            </ErrorBoundary>
          </Layout>
        </BrowserRouter>
      </MarketProvider>
    </QueryClientProvider>
  )
}
