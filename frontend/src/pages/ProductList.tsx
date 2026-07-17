import { Table, Select, Row, Col, Image, Tag, Input, DatePicker, Statistic, Card } from 'antd'
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
  const [categories, setCategories] = useState<string[]>([])
  const [q, setQ] = useState<string>()
  const [date, setDate] = useState<Dayjs | null>(null)
  const [sort, setSort] = useState('monthly_sales')
  const [order, setOrder] = useState<'desc' | 'asc'>('desc')

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
    queryKey: ['products', market, page, brand, categories, q, dateStr, sort, order],
    queryFn: () => unwrap<any>(api.get('/products', {
      params: { page, page_size: 20, market, brand, category: categories.length ? categories : undefined, q, date: dateStr, sort, order },
      paramsSerializer: { indexes: null },
    })),
  })

  const summary = data?.summary

  // 服务端排序：给可排序列加 sorter，并用受控 sortOrder 和下拉框保持同步
  const so = (k: string) => ({
    sorter: true,
    sortOrder: sort === k ? (order === 'asc' ? ('ascend' as const) : ('descend' as const)) : null,
  })

  const columns = [
    { title: '#', width: 55,
      render: (_: any, __: any, i: number) => (page - 1) * 20 + i + 1 },
    { title: '图片', dataIndex: 'main_image', width: 64,
      render: (u: string) => (u ? <Image src={u} width={48} preview={false} /> : '-') },
    { title: '标题', dataIndex: 'product_title', ellipsis: true },
    { title: '品牌', dataIndex: 'brand', width: 110,
      render: (b: string) => { const t = brandTheme(b)
        return <Tag color={t.color}>{t.name}</Tag> } },
    { title: '站点', dataIndex: 'market', width: 70 },
    { title: '价格', dataIndex: 'price', width: 100, ...so('price'),
      render: (v: any) => (v ? `$${v}` : '-') },
    { title: '月销量', dataIndex: 'monthly_sales', width: 100, ...so('monthly_sales') },
    { title: '增长率', dataIndex: 'growth_rate', width: 100, ...so('growth_rate'),
      render: (v: any) => (v == null ? '-' :
        <Tag color={Number(v) >= 0 ? 'green' : 'red'}>{(Number(v) * 100).toFixed(0)}%</Tag>) },
    { title: 'main BSR', dataIndex: 'main_bsr', width: 105, ...so('main_bsr') },
    { title: 'sub BSR', dataIndex: 'sub_bsr', width: 100, ...so('sub_bsr') },
    { title: '评分', dataIndex: 'rating', width: 85, ...so('rating') },
    { title: '配送', dataIndex: 'fulfillment_method', width: 80 },
    { title: '卖家国籍', dataIndex: 'seller_location', width: 95,
      render: (v: any) => v || '-' },
    { title: '上架日期', dataIndex: 'launch_date', width: 120, ...so('launch_date'),
      render: (v: any) => v || '-' },
    { title: '月营收', dataIndex: 'monthly_revenue', width: 115, ...so('monthly_revenue'),
      render: (v: any) => (v != null ? `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '-') },
  ]

  return (
    <div>
      <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
        <Col><Input.Search allowClear placeholder="品牌 / 商品名 / ASIN" style={{ width: 260 }}
          onSearch={(v) => { setQ(v || undefined); setPage(1) }} /></Col>
        <Col><Select allowClear placeholder="品牌" style={{ width: 150 }} value={brand}
          onChange={(v) => { setBrand(v); setPage(1) }}
          options={(brands ?? []).map((b) => ({ value: b, label: b }))} showSearch /></Col>
        <Col><Select allowClear placeholder="品类" mode="multiple" style={{ minWidth: 200, maxWidth: 400 }}
          value={categories}
          onChange={(v) => { setCategories(v); setPage(1) }}
          options={(cats ?? []).map((c) => ({ value: c, label: c }))} showSearch
          maxTagCount={2} /></Col>
        <Col><DatePicker placeholder="快照日期" value={date} style={{ width: 150 }}
          onChange={(d) => { setDate(d); setPage(1) }}
          disabledDate={(d) => d && d > dayjs()} /></Col>
        <Col><Select value={sort} style={{ width: 140 }} onChange={(v) => { setSort(v); setPage(1) }} options={[
          { value: 'monthly_sales', label: '月销量' },
          { value: 'monthly_revenue', label: '月营收' },
          { value: 'price', label: '价格' },
          { value: 'main_bsr', label: 'main BSR' },
          { value: 'rating', label: '评分' },
          { value: 'growth_rate', label: '增长率' },
          { value: 'launch_date', label: '上架时间' },
        ]} /></Col>
        <Col><Select value={order} style={{ width: 90 }} onChange={(v) => { setOrder(v); setPage(1) }} options={[
          { value: 'desc', label: '降序' },
          { value: 'asc', label: '升序' },
        ]} /></Col>
      </Row>
      {summary && (
        <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
          <div style={{ flex: 1, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: 10, padding: '14px 20px', color: '#fff' }}>
            <div style={{ fontSize: 12, opacity: 0.85 }}>商品数</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{Number(summary.product_count).toLocaleString()}</div>
          </div>
          <div style={{ flex: 1, background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            borderRadius: 10, padding: '14px 20px', color: '#fff' }}>
            <div style={{ fontSize: 12, opacity: 0.85 }}>月销量合计</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{Number(summary.total_sales).toLocaleString()}</div>
          </div>
          <div style={{ flex: 1, background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
            borderRadius: 10, padding: '14px 20px', color: '#fff' }}>
            <div style={{ fontSize: 12, opacity: 0.85 }}>月营收合计</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>${Number(summary.total_revenue).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          </div>
          <div style={{ flex: 1, background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
            borderRadius: 10, padding: '14px 20px', color: '#fff' }}>
            <div style={{ fontSize: 12, opacity: 0.85 }}>平均价格</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>${Number(summary.avg_price).toFixed(0)}</div>
          </div>
        </div>
      )}
      <Table rowKey={(r) => `${r.asin}-${r.market}`} loading={isLoading} columns={columns as any}
        dataSource={data?.items ?? []} size="small" scroll={{ x: 1400 }}
        pagination={{ current: page, pageSize: 20, total: data?.total ?? 0,
          showSizeChanger: false, showTotal: (t) => `共 ${t} 条`, onChange: setPage }}
        onChange={(_p, _f, sorter: any, extra: any) => {
          if (extra?.action !== 'sort') return
          const s = Array.isArray(sorter) ? sorter[0] : sorter
          if (s?.order) { setSort(s.field as string); setOrder(s.order === 'ascend' ? 'asc' : 'desc') }
          else { setSort('monthly_sales'); setOrder('desc') }
          setPage(1)
        }}
        onRow={(r) => ({ style: { cursor: 'pointer' },
          onClick: () => nav(`/products/${r.asin}?market=${r.market}`) })} />
    </div>
  )
}
