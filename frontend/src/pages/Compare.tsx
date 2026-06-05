import { Table, Row, Col, Card, Spin, Alert, Empty, Image, Tag } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '../api/client'
import { useMarket } from '../context/MarketContext'
import { brandTheme } from '../theme/brands'

export default function Compare() {
  const { market } = useMarket()
  const { data, isLoading, error } = useQuery({
    queryKey: ['compare', market],
    queryFn: () => unwrap<any>(api.get('/compare', { params: { market } })),
  })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (error) return <Alert type="error" message="加载失败" />
  if (!data?.date) return <Empty description="暂无数据" />

  const brandCols = [
    { title: '品牌', dataIndex: 'brand', render: (b: string) => {
      const t = brandTheme(b)
      return <Tag color={t.color} style={{ fontWeight: 600 }}>{t.name}</Tag>
    } },
    { title: '覆盖站点', dataIndex: 'markets', width: 180, render: (m: string) => m || '—' },
    { title: '商品数', dataIndex: 'product_count' },
    { title: '月销量', dataIndex: 'total_monthly_sales', defaultSortOrder: 'descend' as const,
      sorter: (a: any, b: any) => a.total_monthly_sales - b.total_monthly_sales },
    { title: '月营收', dataIndex: 'total_revenue', render: (v: any) => `$${Number(v).toFixed(0)}` },
    { title: '均价', dataIndex: 'avg_price', render: (v: any) => `$${Number(v).toFixed(2)}` },
    { title: 'FBA占比', dataIndex: 'fba_ratio', render: (v: any) => `${(Number(v) * 100).toFixed(0)}%` },
  ]

  const topCols = [
    { title: '图片', dataIndex: 'main_image', width: 50,
      render: (u: string) => (u ? <Image src={u} width={36} preview={false} /> : '-') },
    { title: '标题', dataIndex: 'product_title', ellipsis: true },
    { title: '月销量', dataIndex: 'monthly_sales', width: 80 },
  ]

  const topProducts: Record<string, any[]> = data.top_products ?? {}

  return (
    <div>
      <Card title={`品牌对比 · ${data.date}`} bordered={false}
            style={{ marginBottom: 20, borderRadius: 14 }}>
        <Table rowKey={(r) => r.brand} columns={brandCols as any}
          dataSource={data.brands ?? []} pagination={false} size="middle" scroll={{ x: 900 }} />
      </Card>
      {/* 品牌卡片:每行3个 */}
      {(() => {
        const entries = Object.entries(topProducts)
        // OUKITEL 置顶
        entries.sort(([a], [b]) => {
          const ao = a.toUpperCase() === 'OUKITEL' ? 0 : 1
          const bo = b.toUpperCase() === 'OUKITEL' ? 0 : 1
          return ao - bo
        })
        const rows: [string, any[]][][] = []
        for (let i = 0; i < entries.length; i += 3) {
          rows.push(entries.slice(i, i + 3))
        }
        const renderCard = ([brand, products]: [string, any[]]) => {
          const t = brandTheme(brand)
          return (
            <Card key={brand}
              bordered={false} style={{ borderRadius: 14, overflow: 'hidden', flex: 1 }}
              styles={{ header: { background: t.gradient, color: '#fff', borderRadius: 0 },
                        body: { padding: 12 } }}
              title={<span style={{ color: '#fff', fontWeight: 700 }}>{t.name} · Top 10</span>}
            >
              <Table rowKey={(r) => `${r.asin}-${r.market}`} columns={topCols as any}
                dataSource={products} pagination={false} size="small" />
            </Card>
          )
        }
        return (
          <>
            {rows.map((row, i) => (
              <div key={i} style={{ display: 'flex', gap: 20, marginBottom: 20 }}>
                {row.map(renderCard)}
              </div>
            ))}
          </>
        )
      })()}
    </div>
  )
}
