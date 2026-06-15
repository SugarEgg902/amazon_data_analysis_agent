import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Card, Spin, Empty, Image, Table, Button, Statistic, Row, Col } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { api, unwrap } from '../api/client'
import { brandTheme } from '../theme/brands'
import PieChart from '../components/PieChart'
import TrendChart from '../components/TrendChart'
import ReactECharts from 'echarts-for-react'

export default function BrandDetail() {
  const { brand } = useParams<{ brand: string }>()
  const navigate = useNavigate()
  const t = brandTheme(brand || '')

  const { data, isLoading } = useQuery({
    queryKey: ['brand-detail', brand],
    queryFn: () => unwrap<any>(api.get(`/brands/${brand}/detail`)),
  })

  if (isLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  }
  if (!data) return <Empty description="暂无数据" />

  const summary = data.summary
  const trend = data.trend || { dates: [], sales: [] }
  const marketDist = data.market_distribution || []
  const categoryCards = data.category_cards || []

  const bucketOrder = ['手机', '平板', '手表', '其他']
  const bucketStyles: Record<string, { bg: string; accent: string }> = {
    '手机': { bg: '#f0f4ff', accent: '#4a6cf7' },
    '平板': { bg: '#f0faf4', accent: '#3da67a' },
    '手表': { bg: '#fdf4f0', accent: '#d4764e' },
    '其他': { bg: '#f5f3ff', accent: '#7c6bbd' },
  }
  const sortedCards = bucketOrder
    .map(name => categoryCards.find((c: any) => c.bucket === name))
    .filter(Boolean)

  const allTotal = categoryCards.reduce((acc: any, c: any) => ({
    total_sales: (acc.total_sales || 0) + Number(c.total_sales || 0),
    total_revenue: (acc.total_revenue || 0) + Number(c.total_revenue || 0),
    product_count: (acc.product_count || 0) + Number(c.product_count || 0),
  }), {})
  const allAvgPrice = allTotal.product_count
    ? categoryCards.reduce((s: number, c: any) => s + Number(c.avg_price || 0) * Number(c.product_count || 0), 0) / allTotal.product_count
    : 0

  const pieData = (data.category_share || []).map((c: any) => ({
    name: c.sub_category,
    value: Number(c.revenue) || 0,
  }))

  const marketBarOption = {
    tooltip: { trigger: 'axis' },
    grid: { top: 20, left: 60, right: 20, bottom: 40 },
    xAxis: { type: 'category', data: marketDist.map((m: any) => m.market) },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: marketDist.map((m: any) => Number(m.sales) || 0),
      itemStyle: { color: t.color, borderRadius: [4, 4, 0, 0] },
    }],
  }

  const columns = [
    {
      title: '图片', dataIndex: 'main_image', width: 70,
      render: (v: string) =>
        v ? <Image src={v} width={50} height={50} style={{ objectFit: 'contain' }} /> : '-',
    },
    {
      title: '标题', dataIndex: 'product_title', ellipsis: true,
      render: (title: string, row: any) => {
        const url = row.product_url || `https://www.amazon.com/dp/${row.asin}`
        return <a href={url} target="_blank" rel="noopener noreferrer">{title || row.asin}</a>
      },
    },
    { title: '站点', dataIndex: 'market', width: 70 },
    { title: '价格', dataIndex: 'price', width: 80,
      render: (v: any) => (v != null ? `$${Number(v).toFixed(0)}` : '-') },
    { title: '月销量', dataIndex: 'monthly_sales', width: 90,
      render: (v: any) => (v != null ? Number(v).toLocaleString() : '-') },
    { title: '月营收', dataIndex: 'monthly_revenue', width: 100,
      render: (v: any) => v != null ? `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '-' },
  ]

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/overview')}
        style={{ marginBottom: 16 }}>
        返回市场概览
      </Button>

      {/* 品牌 Header */}
      <Card
        bordered={false}
        styles={{ header: { background: t.gradient, color: '#fff', border: 'none' }, body: { padding: 20 } }}
        title={
          <div style={{ color: '#fff' }}>
            <span style={{ fontSize: 24, fontWeight: 700 }}>{t.name}</span>
            <span style={{ marginLeft: 12, fontSize: 13, opacity: 0.92 }}>{t.intro}</span>
            {data.date && <span style={{ marginLeft: 12, fontSize: 12, opacity: 0.8 }}>· {data.date}</span>}
          </div>
        }
        style={{ borderRadius: 14, overflow: 'hidden', marginBottom: 20 }}
      >
        {/* 全品类概览指标 */}
        {categoryCards.length > 0 && (
          <Row gutter={[16, 16]}>
            <Col span={4}><Statistic title="月销量" value={allTotal.total_sales} /></Col>
            <Col span={4}><Statistic title="月营收 (USD)" value={allTotal.total_revenue}
              precision={0} prefix="$" /></Col>
            <Col span={4}><Statistic title="SKU 数" value={allTotal.product_count} /></Col>
            <Col span={4}><Statistic title="均价 (USD)" value={allAvgPrice}
              precision={0} prefix="$" /></Col>
            <Col span={4}><Statistic title="评分" value={summary?.avg_rating} precision={2} /></Col>
            <Col span={4}><Statistic title="覆盖站点" value={summary?.markets} /></Col>
          </Row>
        )}
      </Card>

      {/* 品类数据卡片 */}
      {sortedCards.length > 0 && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
          {sortedCards.map((c: any) => {
            const bs = bucketStyles[c.bucket] || bucketStyles['其他']
            const clickable = c.bucket === '手机' || c.bucket === '平板'
            return (
              <div key={c.bucket}
                onClick={clickable ? () => navigate(`/brands/${brand}/models/${c.bucket}`) : undefined}
                style={{
                  flex: 1, background: bs.bg, border: `1px solid ${bs.accent}22`,
                  borderRadius: 10, padding: '14px 16px',
                  cursor: clickable ? 'pointer' : 'default',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                }}
                onMouseEnter={clickable ? (e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)' } : undefined}
                onMouseLeave={clickable ? (e) => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '' } : undefined}
              >
                <div style={{ fontSize: 14, fontWeight: 600, color: bs.accent, marginBottom: 8 }}>{c.bucket}</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: 12, color: '#555' }}>
                  <div><span style={{ color: '#999' }}>月销量</span><div style={{ fontSize: 16, fontWeight: 600, color: '#333' }}>{Number(c.total_sales || 0).toLocaleString()}</div></div>
                  <div><span style={{ color: '#999' }}>月营收</span><div style={{ fontSize: 16, fontWeight: 600, color: '#333' }}>${Number(c.total_revenue || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div></div>
                  <div><span style={{ color: '#999' }}>SKU</span><div style={{ fontWeight: 600, color: '#333' }}>{c.product_count}</div></div>
                  <div><span style={{ color: '#999' }}>均价</span><div style={{ fontWeight: 600, color: '#333' }}>${Number(c.avg_price || 0).toFixed(0)}</div></div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 30天趋势 + 站点分布 */}
      <Row gutter={20} style={{ marginBottom: 20 }}>
        <Col span={14}>
          <Card title="30 天月销量趋势" bordered={false} style={{ borderRadius: 14 }}>
            {trend.dates.length > 0 ? (
              <TrendChart dates={trend.dates}
                series={{ [t.name]: trend.sales }}
                colors={{ [t.name]: t.color }}
                height={280} />
            ) : (
              <Empty description="暂无趋势数据" />
            )}
          </Card>
        </Col>
        <Col span={10}>
          <Card title="各站点月销量分布" bordered={false} style={{ borderRadius: 14 }}>
            {marketDist.length > 0 ? (
              <ReactECharts option={marketBarOption} style={{ height: 280 }} notMerge />
            ) : (
              <Empty description="暂无站点数据" />
            )}
          </Card>
        </Col>
      </Row>

      {/* 品类营收占比 */}
      <Card title="品类营收占比 (Top 10)" bordered={false}
        style={{ borderRadius: 14, marginBottom: 20 }}>
        {pieData.length > 0 ? (
          <PieChart data={pieData} height={360} />
        ) : (
          <Empty description="暂无品类数据" />
        )}
      </Card>

      {/* Top 10 手机商品 */}
      <Card
        title={<span style={{ color: '#fff', fontWeight: 700 }}>{t.name} · 手机品类销量 Top 10</span>}
        bordered={false}
        styles={{ header: { background: t.gradient, border: 'none' }, body: { padding: 12 } }}
        style={{ borderRadius: 14, overflow: 'hidden' }}
      >
        {data.top_products && data.top_products.length > 0 ? (
          <Table rowKey={(r) => `${r.asin}-${r.market}`}
            columns={columns as any} dataSource={data.top_products}
            pagination={false} size="small" />
        ) : (
          <Empty description="暂无手机品类商品" />
        )}
      </Card>
    </div>
  )
}
