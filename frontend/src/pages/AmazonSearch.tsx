import { Input, Table, Spin, Empty, Card, Tag, message, Radio, Space } from 'antd'
import { useState } from 'react'
import { api } from '../api/client'

const { Search } = Input

const SOURCE_OPTIONS = [
  { value: 'amazon', label: 'Amazon 爬虫' },
  { value: 'sellersprite', label: '卖家精灵' },
]

const sellerSpriteCols = [
  { title: 'ASIN', dataIndex: 'asin', width: 110,
    render: (v: string) => <a href={`https://www.amazon.com/dp/${v}`} target="_blank" rel="noopener noreferrer">{v}</a> },
  { title: '商品图', dataIndex: 'imageUrl', width: 70,
    render: (v: string) => v ? <img src={v} style={{ width: 50, height: 50, objectFit: 'contain' }} /> : '-' },
  { title: '标题', dataIndex: 'title', ellipsis: true, width: 250 },
  { title: '品牌', dataIndex: 'brand', width: 100 },
  { title: '价格', dataIndex: 'price', width: 80, render: (v: any) => v != null ? `$${v}` : '-' },
  { title: '月销量', dataIndex: 'totalUnits', width: 90, sorter: (a: any, b: any) => (a.totalUnits || 0) - (b.totalUnits || 0) },
  { title: '月营收', dataIndex: 'totalAmount', width: 100,
    render: (v: any) => v != null ? `$${Number(v).toLocaleString()}` : '-' },
  { title: '评分', dataIndex: 'rating', width: 60 },
  { title: '评论数', dataIndex: 'reviews', width: 80 },
  { title: 'BSR', dataIndex: 'bsrRank', width: 80 },
  { title: '类目', dataIndex: 'categoryName', width: 140, ellipsis: true },
  { title: '卖家', dataIndex: 'sellerName', width: 100, ellipsis: true },
  { title: 'FBA', dataIndex: 'fba', width: 60, render: (v: boolean) => v ? '是' : '否' },
  { title: '上架时间', dataIndex: 'availableDate', width: 100,
    render: (v: any) => v ? new Date(v).toLocaleDateString() : '-' },
]

const playColumns = [
  { title: 'ASIN', dataIndex: 'asin', width: 120 },
  { title: '标题', dataIndex: 'title', ellipsis: true,
    render: (t: string, row: any) => row.url
      ? <a href={row.url} target="_blank" rel="noopener noreferrer">{t || row.asin}</a>
      : (t || '-') },
  { title: '价格', dataIndex: 'price', width: 100 },
  { title: '评分', dataIndex: 'rating', width: 120 },
  { title: 'BSR', dataIndex: 'bsr_display', width: 180,
    render: (v: string) => v || '-' },
  { title: '月销估算', dataIndex: 'monthly_sales_estimate', width: 100,
    render: (v: any) => v || '-' },
  { title: '月营收估算', dataIndex: 'monthly_revenue_estimate', width: 120,
    render: (v: any) => v ? `$${v}` : '-' },
  { title: '状态', dataIndex: 'is_valid', width: 80,
    render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '有效' : '无效'}</Tag> },
]

export default function AmazonSearch() {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<any>(null)
  const [source, setSource] = useState('amazon')
  const [items, setItems] = useState<any[]>([])
  const [columns, setColumns] = useState<any[]>(playColumns)

  const onSearch = async (keyword: string) => {
    console.log('[AmazonSearch] onSearch called', keyword, source)
    if (!keyword.trim()) return
    setLoading(true)
    setData(null)
    setItems([])
    try {
      if (source === 'amazon') {
        const res = await api.get('/search', { params: { keyword }, timeout: 300000 })
        console.log('[AmazonSearch] response', res.data)
        setData(res.data?.data)
        if (res.data?.data?.products) {
          setColumns(playColumns)
          setItems(res.data.data.products)
        }
      } else {
        const res = await api.get('/sellersprite', { params: { keyword }, timeout: 30000 })
        const raw = res.data?.data
        const list = raw?.data?.items || raw?.items || []
        if (list.length > 0) {
          setColumns(sellerSpriteCols)
          setItems(list)
        }
        setData(raw)
      }
    } catch (e: any) {
      console.error('[AmazonSearch] error', e)
      const detail = e?.response?.data?.detail || e?.message || '搜索失败'
      if (e?.response?.status === 401) {
        message.warning(detail, 10)
      } else {
        message.error(detail)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Card bordered={false} style={{ borderRadius: 14, marginBottom: 20 }}>
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Radio.Group
            optionType="button" buttonStyle="solid"
            value={source} onChange={(e) => { setSource(e.target.value); setData(null); setItems([]) }}
            options={SOURCE_OPTIONS}
          />
          <Search
            placeholder={source === 'amazon'
              ? '输入关键词爬取 Amazon 商品'
              : '输入关键词搜索卖家精灵竞品数据'}
            enterButton="搜索"
            size="large"
            loading={loading}
            onSearch={onSearch}
            allowClear
          />
        </Space>
      </Card>
      {loading && <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />}
      {!loading && items.length > 0 && (
        <Card bordered={false} style={{ borderRadius: 14 }}>
          <Table rowKey={(r, i) => r.asin || r.id || String(i)}
            columns={columns as any} dataSource={items}
            size="small" pagination={{ pageSize: 20 }}
            scroll={{ x: 1200 }} />
        </Card>
      )}
      {!loading && data && items.length === 0 && !data.products && (
        <Empty description="未找到商品" />
      )}
    </div>
  )
}
