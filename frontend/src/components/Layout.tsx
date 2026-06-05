import { Layout as AntLayout, Menu, Select, Space, Typography } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  DashboardOutlined, UnorderedListOutlined, SwapOutlined,
  RiseOutlined, AlertOutlined, FileTextOutlined, BarChartOutlined, SearchOutlined,
} from '@ant-design/icons'
import { api, unwrap } from '../api/client'
import { useMarket } from '../context/MarketContext'

const { Sider, Content, Header } = AntLayout

const items = [
  { key: '/overview', icon: <DashboardOutlined />, label: '市场概览' },
  { key: '/products', icon: <UnorderedListOutlined />, label: '商品列表' },
  { key: '/compare', icon: <SwapOutlined />, label: '竞品对比' },
  { key: '/trends', icon: <RiseOutlined />, label: '趋势分析' },
  { key: '/anomalies', icon: <AlertOutlined />, label: '异常检测' },
  { key: '/reports', icon: <FileTextOutlined />, label: '每日报告' },
  { key: '/sales-analysis', icon: <BarChartOutlined />, label: '销售分析' },
  { key: '/search', icon: <SearchOutlined />, label: 'Amazon搜索' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const nav = useNavigate()
  const { pathname } = useLocation()
  const { market, setMarket } = useMarket()
  const { data: markets } = useQuery({
    queryKey: ['markets'],
    queryFn: () => unwrap<string[]>(api.get('/meta/markets')),
  })
  const selectedKey = '/' + (pathname.split('/')[1] || 'overview')

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={200}
        style={{ position: 'fixed', insetInlineStart: 0, top: 0, bottom: 0,
                 height: '100vh', overflow: 'auto', zIndex: 100 }}>
        <div style={{ color: '#fff', padding: 16, fontWeight: 'bold', fontSize: 16 }}>
          Amazon Analytics
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[selectedKey]}
              items={items} onClick={({ key }) => nav(key)} />
      </Sider>
      <AntLayout style={{ marginInlineStart: 200 }}>
        <Header style={{ background: '#fff', padding: '0 24px', display: 'flex',
                         alignItems: 'center', justifyContent: 'flex-end',
                         position: 'sticky', top: 0, zIndex: 99 }}>
          <Space>
            <Typography.Text type="secondary">站点</Typography.Text>
            <Select
              placeholder="全部站点" style={{ width: 160 }}
              value={market || 'all'}
              onChange={(v) => setMarket(v === 'all' ? undefined : v)}
              options={[
                { value: 'all', label: '全部站点' },
                ...(markets ?? []).map((m) => ({ value: m, label: m })),
              ]}
            />
          </Space>
        </Header>
        <Content style={{ padding: 24, background: '#f5f5f5' }}>{children}</Content>
      </AntLayout>
    </AntLayout>
  )
}
