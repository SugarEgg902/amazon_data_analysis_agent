import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Card, Spin, Empty, Button, Table } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { api, unwrap } from '../api/client'
import { brandTheme } from '../theme/brands'

export default function ModelRanking() {
  const { brand, type } = useParams<{ brand: string; type: string }>()
  const navigate = useNavigate()
  const t = brandTheme(brand || '')
  const [selectedModel, setSelectedModel] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['brand-models', brand, type],
    queryFn: () => unwrap<any>(api.get(`/brands/${brand}/models`, { params: { type } })),
  })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (!data || !data.models?.length) return <Empty description="暂无型号数据" />

  const models = data.models
  const active = selectedModel || models[0]?.model
  const activeData = models.find((m: any) => m.model === active)

  const barOption = activeData ? {
    tooltip: { trigger: 'axis' },
    grid: { top: 20, left: 50, right: 20, bottom: 40 },
    xAxis: {
      type: 'category',
      data: activeData.markets.sort((a: any, b: any) => b.sales - a.sales).map((m: any) => m.market),
    },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: activeData.markets.sort((a: any, b: any) => b.sales - a.sales).map((m: any) => m.sales),
      itemStyle: { color: t.color, borderRadius: [4, 4, 0, 0] },
    }],
  } : null

  const columns = [
    { title: '#', width: 50, render: (_: any, __: any, i: number) => i + 1 },
    { title: '型号', dataIndex: 'model', width: 160 },
    { title: '月销量', dataIndex: 'total_sales', width: 100,
      render: (v: number) => Number(v).toLocaleString() },
    { title: '月营收', dataIndex: 'total_revenue', width: 110,
      render: (v: number) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}` },
    { title: 'SKU', dataIndex: 'sku_count', width: 70 },
    { title: '站点数', width: 70,
      render: (_: any, row: any) => row.markets?.length || 0 },
  ]

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/brands/${brand}`)}
        style={{ marginBottom: 16 }}>
        返回品牌详情
      </Button>

      <div style={{ display: 'flex', gap: 20 }}>
        {/* 左侧：型号排名表 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Card
            title={
              <span style={{ color: '#fff', fontWeight: 700 }}>
                {t.name} · {type}型号排名
              </span>
            }
            bordered={false}
            styles={{ header: { background: t.gradient, border: 'none' }, body: { padding: 0 } }}
            style={{ borderRadius: 14, overflow: 'hidden' }}
          >
            <Table
              rowKey="model"
              columns={columns as any}
              dataSource={models}
              pagination={false}
              size="small"
              scroll={{ y: 500 }}
              onRow={(row) => ({
                onClick: () => setSelectedModel(row.model),
                style: {
                  cursor: 'pointer',
                  background: row.model === active ? '#f0f5ff' : undefined,
                },
              })}
            />
          </Card>
        </div>

        {/* 右侧：各站点销量图表 */}
        <div style={{ width: 420 }}>
          <Card
            title={active ? `${active} · 各站点销量` : '选择型号查看'}
            bordered={false}
            style={{ borderRadius: 14, position: 'sticky', top: 20 }}
          >
            {barOption ? (
              <ReactECharts option={barOption} style={{ height: 320 }} notMerge />
            ) : (
              <Empty description="点击左侧型号查看" />
            )}
            {activeData && (
              <div style={{ marginTop: 12, padding: '0 4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#666', marginBottom: 6 }}>
                  <span>总销量: <b style={{ color: '#333' }}>{Number(activeData.total_sales).toLocaleString()}</b></span>
                  <span>总营收: <b style={{ color: '#333' }}>${Number(activeData.total_revenue).toLocaleString(undefined, { maximumFractionDigits: 0 })}</b></span>
                </div>
                <div style={{ fontSize: 12, color: '#999' }}>
                  覆盖 {activeData.markets.length} 个站点 · {activeData.sku_count} 个 SKU
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
