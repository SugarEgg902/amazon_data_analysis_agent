import { Input, Table, Spin, Empty, Card, message } from 'antd'
import { useState } from 'react'
import { api } from '../api/client'

const { Search } = Input

const columns = [
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

export default function AmazonSearch() {
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<any[]>([])
  const [searched, setSearched] = useState(false)

  const onSearch = async (keyword: string) => {
    if (!keyword.trim()) return
    setLoading(true)
    setItems([])
    setSearched(true)
    try {
      const res = await api.get('/sellersprite', { params: { keyword }, timeout: 30000 })
      const raw = res.data?.data
      const list = raw?.data?.items || raw?.items || []
      setItems(list)
    } catch (e: any) {
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
        <Search
          placeholder="输入关键词搜索竞品数据"
          enterButton="搜索"
          size="large"
          loading={loading}
          onSearch={onSearch}
          allowClear
        />
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
      {!loading && searched && items.length === 0 && (
        <Empty description="未找到商品" />
      )}
    </div>
  )
}

