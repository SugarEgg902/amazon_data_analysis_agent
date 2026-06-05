import { Table, Select, Row, Col, Image, Tag, Input, DatePicker } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import dayjs, { Dayjs } from 'dayjs'
import { api, unwrap } from '../api/client'
import { useMarket } from '../context/MarketContext'
import { brandTheme } from '../theme/brands'

export default function ProductList() {
  const nav = useNavigate()
  const { market } = useMarket()
  const [page, setPage] = useState(1)
  const [brand, setBrand] = useState<string>()
  const [category, setCategory] = useState<string>()
  const [q, setQ] = useState<string>()
  const [date, setDate] = useState<Dayjs | null>(null)
  const [sort, setSort] = useState('monthly_sales')

  const dateStr = date ? date.format('YYYY-MM-DD') : undefined

  const { data: brands } = useQuery({
    queryKey: ['brands', market],
    queryFn: () => unwrap<string[]>(api.get('/meta/brands', { params: { market } })),
  })
  const { data: cats } = useQuery({
    queryKey: ['cats', market],
    queryFn: () => unwrap<string[]>(api.get('/meta/categories', { params: { market } })),
  })
  const { data, isLoading } = useQuery({
    queryKey: ['products', market, page, brand, category, q, dateStr, sort],
    queryFn: () => unwrap<any>(api.get('/products', {
      params: { page, page_size: 20, market, brand, category, q, date: dateStr, sort },
    })),
  })

  const columns = [
    { title: '图片', dataIndex: 'main_image', width: 64,
      render: (u: string) => (u ? <Image src={u} width={48} preview={false} /> : '-') },
    { title: '标题', dataIndex: 'product_title', ellipsis: true },
    { title: '品牌', dataIndex: 'brand', width: 110,
      render: (b: string) => { const t = brandTheme(b)
        return <Tag color={t.color}>{t.name}</Tag> } },
    { title: '站点', dataIndex: 'market', width: 70 },
    { title: '价格', dataIndex: 'price', width: 90, render: (v: any) => (v ? `$${v}` : '-') },
    { title: '月销量', dataIndex: 'monthly_sales', width: 90 },
    { title: '增长率', dataIndex: 'growth_rate', width: 90,
      render: (v: any) => (v == null ? '-' :
        <Tag color={Number(v) >= 0 ? 'green' : 'red'}>{(Number(v) * 100).toFixed(0)}%</Tag>) },
    { title: 'main BSR', dataIndex: 'main_bsr', width: 90 },
    { title: 'sub BSR', dataIndex: 'sub_bsr', width: 90 },
    { title: '评分', dataIndex: 'rating', width: 70 },
    { title: '配送', dataIndex: 'fulfillment_method', width: 80 },
    { title: '增长率', dataIndex: 'growth_rate', width: 80,
      render: (v: any) => (v == null ? '-' : `${(Number(v) * 100).toFixed(0)}%`) },
  ]

  return (
    <div>
      <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
        <Col><Input.Search allowClear placeholder="品牌 / 商品名 / ASIN" style={{ width: 260 }}
          onSearch={(v) => { setQ(v || undefined); setPage(1) }} /></Col>
        <Col><Select allowClear placeholder="品牌" style={{ width: 150 }} value={brand}
          onChange={(v) => { setBrand(v); setPage(1) }}
          options={(brands ?? []).map((b) => ({ value: b, label: b }))} showSearch /></Col>
        <Col><Select allowClear placeholder="品类" style={{ width: 200 }} value={category}
          onChange={(v) => { setCategory(v); setPage(1) }}
          options={(cats ?? []).map((c) => ({ value: c, label: c }))} showSearch /></Col>
        <Col><DatePicker placeholder="快照日期" value={date} style={{ width: 150 }}
          onChange={(d) => { setDate(d); setPage(1) }}
          disabledDate={(d) => d && d > dayjs()} /></Col>
        <Col><Select value={sort} style={{ width: 140 }} onChange={setSort} options={[
          { value: 'monthly_sales', label: '月销量' },
          { value: 'monthly_revenue', label: '月营收' },
          { value: 'price', label: '价格' },
          { value: 'main_bsr', label: 'main BSR' },
          { value: 'rating', label: '评分' },
          { value: 'growth_rate', label: '增长率' },
        ]} /></Col>
      </Row>
      <Table rowKey={(r) => `${r.asin}-${r.market}`} loading={isLoading} columns={columns as any}
        dataSource={data?.items ?? []} size="small" scroll={{ x: 1200 }}
        pagination={{ current: page, pageSize: 20, total: data?.total ?? 0,
          showSizeChanger: false, showTotal: (t) => `共 ${t} 条`, onChange: setPage }}
        onRow={(r) => ({ style: { cursor: 'pointer' },
          onClick: () => nav(`/products/${r.asin}?market=${r.market}`) })} />
    </div>
  )
}
