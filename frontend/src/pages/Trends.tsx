import { Table, Tabs, Tag, Image, Spin, Alert, Empty, Select, Space } from 'antd'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, unwrap } from '../api/client'
import { useMarket } from '../context/MarketContext'
import PieChart from '../components/PieChart'

export default function Trends() {
  const nav = useNavigate()
  const { market } = useMarket()
  // 新品追踪:上架时间在最近 N 天内
  const [newDays, setNewDays] = useState(30)
  const [activeTab, setActiveTab] = useState('1')
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['trends', market, newDays],
    queryFn: () => unwrap<any>(api.get('/trends', { params: { market, new_days: newDays } })),
    // 切换筛选时保留旧数据,避免整页变成 Spin 导致 Tabs 重置回第一个标签
    placeholderData: keepPreviousData,
  })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (error) return <Alert type="error" message="加载失败" />
  if (!data?.date) return <Empty description="暂无数据" />

  const growthCols = [
    { title: '#', render: (_: any, __: any, i: number) => i + 1, width: 50 },
    { title: '图片', dataIndex: 'main_image', width: 56,
      render: (u: string) => (u ? <Image src={u} width={40} preview={false} /> : '-') },
    { title: '标题', dataIndex: 'product_title', ellipsis: true },
    { title: '品牌', dataIndex: 'brand', width: 110 },
    { title: '站点', dataIndex: 'market', width: 70 },
    { title: '增长率', dataIndex: 'growth_rate', width: 100,
      render: (v: any) => <Tag color={Number(v) >= 0 ? 'green' : 'red'}>{(Number(v) * 100).toFixed(0)}%</Tag> },
    { title: '月销量', dataIndex: 'monthly_sales', width: 90 },
  ]

  const newCols = [
    { title: '图片', dataIndex: 'main_image', width: 56,
      render: (u: string) => (u ? <Image src={u} width={40} preview={false} /> : '-') },
    { title: '标题', dataIndex: 'product_title', ellipsis: true },
    { title: '品牌', dataIndex: 'brand', width: 110 },
    { title: '站点', dataIndex: 'market', width: 70 },
    { title: '上架日期', dataIndex: 'launch_date', width: 120 },
    { title: '价格', dataIndex: 'price', width: 90, render: (v: any) => (v ? `$${v}` : '-') },
  ]

  const pie = (data.category_trends ?? []).map((c: any) => ({
    name: c.sub_category, value: Number(c.total_sales) || 0,
  }))

  const items = [
    { key: '1', label: '增长率排行',
      children: <Table rowKey={(r: any) => `${r.asin}-${r.market}`} columns={growthCols as any}
        dataSource={data.growth_ranking ?? []} pagination={{ pageSize: 20 }} size="small"
        onRow={(r: any) => ({ style: { cursor: 'pointer' },
          onClick: () => nav(`/products/${r.asin}?market=${r.market}`) })} /> },
    { key: '2', label: '新品追踪',
      children: (
        <div>
          <Space style={{ marginBottom: 12 }}>
            <span>上架时间</span>
            <Select value={newDays} style={{ width: 130 }} onChange={setNewDays}
              options={[
                { value: 7, label: '最近 7 天' },
                { value: 14, label: '最近 14 天' },
                { value: 30, label: '最近 30 天' },
                { value: 60, label: '最近 60 天' },
                { value: 90, label: '最近 90 天' },
                { value: 180, label: '最近 180 天' },
              ]} />
          </Space>
          <Table rowKey={(r: any) => `${r.asin}-${r.market}`} columns={newCols as any}
            dataSource={data.new_products ?? []} pagination={{ pageSize: 20 }} size="small"
            loading={isFetching}
            onRow={(r: any) => ({ style: { cursor: 'pointer' },
              onClick: () => nav(`/products/${r.asin}?market=${r.market}`) })} />
        </div>
      ) },
    { key: '3', label: '品类热度',
      children: <PieChart data={pie} title="月销量品类分布" height={420} /> },
  ]

  return <Tabs items={items} activeKey={activeTab} onChange={setActiveTab} />
}
