import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Descriptions, Image, Button, Spin, Alert, Row, Col, Card, Tag, Space } from 'antd'
import { api, unwrap } from '../api/client'
import TrendChart from '../components/TrendChart'

export default function ProductDetail() {
  const { asin } = useParams<{ asin: string }>()
  const [sp] = useSearchParams()
  const market = sp.get('market') || undefined
  const nav = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['product', asin, market],
    queryFn: () => unwrap<any>(api.get(`/products/${asin}`, { params: { market } })),
  })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (error) return <Alert type="error" message="商品不存在" />

  const h = data?.history ?? []
  const dates = h.map((x: any) => x.snapshot_date)
  const priceSeries = { 价格: h.map((x: any) => Number(x.price) || 0) }
  const salesSeries = { 月销量: h.map((x: any) => Number(x.monthly_sales) || 0) }
  const bsrSeries = {
    'main BSR': h.map((x: any) => Number(x.main_bsr) || 0),
    'sub BSR': h.map((x: any) => Number(x.sub_bsr) || 0),
  }

  return (
    <div>
      <Button onClick={() => nav(-1)} style={{ marginBottom: 16 }}>← 返回</Button>
      <Row gutter={24}>
        <Col xs={24} md={6}>
          {data?.main_image && <Image src={data.main_image} width="100%" />}
        </Col>
        <Col xs={24} md={18}>
          <Descriptions bordered size="small" column={2} title={data?.product_title}>
            <Descriptions.Item label="ASIN">{data?.asin}</Descriptions.Item>
            <Descriptions.Item label="父ASIN">{data?.parent_asin || '-'}</Descriptions.Item>
            <Descriptions.Item label="品牌">{data?.brand}</Descriptions.Item>
            <Descriptions.Item label="站点">{data?.market}</Descriptions.Item>
            <Descriptions.Item label="大类">{data?.main_category}</Descriptions.Item>
            <Descriptions.Item label="小类">{data?.sub_category}</Descriptions.Item>
            <Descriptions.Item label="价格">{data?.price ? `$${data.price}` : '-'}</Descriptions.Item>
            <Descriptions.Item label="月销量">{data?.monthly_sales}</Descriptions.Item>
            <Descriptions.Item label="main BSR">{data?.main_bsr}</Descriptions.Item>
            <Descriptions.Item label="sub BSR">{data?.sub_bsr}</Descriptions.Item>
            <Descriptions.Item label="配送方式">{data?.fulfillment_method}</Descriptions.Item>
            <Descriptions.Item label="卖家产地">{data?.seller_location}</Descriptions.Item>
            <Descriptions.Item label="BuyBox卖家">{data?.buybox_seller || '-'}</Descriptions.Item>
            <Descriptions.Item label="毛利率">
              {data?.gross_margin != null ? `${(Number(data.gross_margin) * 100).toFixed(0)}%` : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="上架日期">{data?.launch_date || '-'}</Descriptions.Item>
            <Descriptions.Item label="在售天数">{data?.days_on_market || '-'}</Descriptions.Item>
            <Descriptions.Item label="重量/尺寸" span={2}>
              <Space>{data?.product_weight} {data?.product_dimensions}</Space>
            </Descriptions.Item>
          </Descriptions>
        </Col>
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col xs={24} lg={8}><Card title="历史价格"><TrendChart dates={dates} series={priceSeries} height={240} /></Card></Col>
        <Col xs={24} lg={8}><Card title="月销量走势"><TrendChart dates={dates} series={salesSeries} height={240} /></Card></Col>
        <Col xs={24} lg={8}><Card title="BSR 走势"><TrendChart dates={dates} series={bsrSeries} height={240} /></Card></Col>
      </Row>
    </div>
  )
}
