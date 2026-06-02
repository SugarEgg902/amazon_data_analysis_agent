import { Table, Tabs, Tag, Image, Spin, Alert, Empty } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '../api/client'
import { useMarket } from '../context/MarketContext'
import PieChart from '../components/PieChart'

export default function Trends() {
  const { market } = useMarket()
  const { data, isLoading, error } = useQuery({
    queryKey: ['trends', market],
    queryFn: () => unwrap<any>(api.get('/trends', { params: { market } })),
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
        dataSource={data.growth_ranking ?? []} pagination={{ pageSize: 20 }} size="small" /> },
    { key: '2', label: '新品追踪',
      children: <Table rowKey={(r: any) => `${r.asin}-${r.market}`} columns={newCols as any}
        dataSource={data.new_products ?? []} pagination={{ pageSize: 20 }} size="small" /> },
    { key: '3', label: '品类热度',
      children: <PieChart data={pie} title="月销量品类分布" height={420} /> },
  ]

  return <Tabs items={items} />
}
