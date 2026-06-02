import { Row, Col, Card, Statistic, Spin, Alert, Empty, Tag, Tooltip } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '../api/client'
import { brandTheme } from '../theme/brands'
import TrendChart from '../components/TrendChart'
import PieChart from '../components/PieChart'

export default function Overview() {
  // 市场概览只按品牌聚类、跨所有站点合并,刻意不跟随顶部站点开关
  const { data, isLoading, error } = useQuery({
    queryKey: ['overview'],
    queryFn: () => unwrap<any>(api.get('/overview')),
  })
  const { data: trend } = useQuery({
    queryKey: ['brands-trend'],
    queryFn: () => unwrap<any>(api.get('/brands/trend', { params: { days: 30 } })),
  })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (error) return <Alert type="error" message="加载失败" />
  if (!data?.date) return <Empty description="暂无聚合数据" />

  // OUKITEL 置顶,其余按营收(后端已降序)保持
  const brands = [...(data.brands ?? [])].sort((a: any, b: any) => {
    const ao = a.brand?.toUpperCase() === 'OUKITEL' ? 0 : 1
    const bo = b.brand?.toUpperCase() === 'OUKITEL' ? 0 : 1
    return ao - bo
  })
  const pie = (data.category_share ?? []).map((c: any) => ({
    name: c.sub_category, value: Number(c.revenue) || 0,
  }))

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 16, fontWeight: 600 }}>市场概览</span>
        <Tag color="geekblue">类别: {data.category}</Tag>
        <span style={{ color: '#999', fontSize: 12 }}>按品牌聚类 · 全站点合并 · {data.date}</span>
      </div>
      <div style={{ display: 'flex', gap: 20, overflowX: 'auto', paddingBottom: 12,
                    marginBottom: 20, scrollSnapType: 'x mandatory' }}>
        {brands.map((b: any) => {
          const t = brandTheme(b.brand)
          return (
            <div key={b.brand} style={{ flex: '0 0 320px', scrollSnapAlign: 'start' }}>
              <Card
                hoverable bordered={false}
                styles={{ body: { padding: 0 } }}
                style={{ borderRadius: 14, overflow: 'hidden',
                         boxShadow: '0 4px 16px rgba(0,0,0,0.08)' }}
              >
                <div style={{ background: t.gradient, padding: '18px 20px', color: '#fff' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 22, fontWeight: 700, letterSpacing: 0.5 }}>{t.name}</span>
                    <Tag color="rgba(255,255,255,0.25)" style={{ color: '#fff', border: 'none' }}>
                      {b.product_count} SKU
                    </Tag>
                  </div>
                  <div style={{ fontSize: 12, opacity: 0.92, marginTop: 6, minHeight: 32 }}>{t.intro}</div>
                  <div style={{ fontSize: 11, opacity: 0.8, marginTop: 6 }}>
                    覆盖站点: {b.markets || '—'}
                  </div>
                </div>
                <div style={{ padding: '16px 20px' }}>
                  <Row gutter={[12, 14]}>
                    <Col span={12}><Statistic title="月销量" value={b.total_monthly_sales}
                      valueStyle={{ color: t.color, fontSize: 20 }} /></Col>
                    <Col span={12}><Statistic title="月营收" value={Number(b.total_revenue)}
                      precision={0} prefix="$" valueStyle={{ fontSize: 20 }} /></Col>
                    <Col span={8}><Statistic title="均价" value={Number(b.avg_price)} precision={0} prefix="$"
                      valueStyle={{ fontSize: 15 }} /></Col>
                    <Col span={8}>
                      <Tooltip title="平均评分">
                        <Statistic title="评分" value={Number(b.avg_rating)} precision={2}
                          valueStyle={{ fontSize: 15 }} />
                      </Tooltip>
                    </Col>
                    <Col span={8}><Statistic title="毛利率" value={Number(b.avg_gross_margin) * 100}
                      precision={0} suffix="%" valueStyle={{ fontSize: 15 }} /></Col>
                  </Row>
                </div>
              </Card>
            </div>
          )
        })}
      </div>
      <Row gutter={[20, 20]}>
        <Col xs={24} lg={14}>
          <Card title="30天月销量趋势" bordered={false} style={{ borderRadius: 14 }}>
            {trend && <TrendChart dates={trend.dates} series={trend.series}
              colors={Object.fromEntries(
                Object.keys(trend.series).map((b: string) => [b, brandTheme(b).color])
              )} />}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="品类营收占比 (Top 10)" bordered={false} style={{ borderRadius: 14 }}>
            <PieChart data={pie} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
