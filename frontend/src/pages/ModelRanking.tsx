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
      label: { show: true, position: 'top', fontSize: 11, color: '#555' },
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

      <div style={{ display: 'flex', gap: 20, alignItems: 'stretch' }}>
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
              scroll={{ y: 620 }}
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

        {/* 右侧：各站点销量图表 + 国家占比 + 参数 */}
        <div style={{ width: 480, display: 'flex', flexDirection: 'column' }}>
          <Card
            title={active ? `${active}` : '选择型号查看'}
            bordered={false}
            style={{ borderRadius: 14, flex: 1, display: 'flex', flexDirection: 'column' }}
            styles={{ body: { padding: '16px 20px', flex: 1, display: 'flex', flexDirection: 'column' } }}
          >
            {barOption ? (
              <ReactECharts option={barOption} style={{ flex: 1, minHeight: 200 }} notMerge />
            ) : (
              <Empty description="点击左侧型号查看" />
            )}
            {activeData && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#666', margin: '12px 0' }}>
                  <span>总销量: <b style={{ color: '#333' }}>{Number(activeData.total_sales).toLocaleString()}</b></span>
                  <span>总营收: <b style={{ color: '#333' }}>${Number(activeData.total_revenue).toLocaleString(undefined, { maximumFractionDigits: 0 })}</b></span>
                  <span style={{ color: '#999' }}>{activeData.markets.length} 站点 · {activeData.sku_count} SKU</span>
                </div>

                {/* 国家占比 + 型号参数 并排 */}
                <div style={{ display: 'flex', gap: 14, marginTop: 10 }}>
                  {/* 国家占比 */}
                  <div style={{ flex: 1, padding: '12px 14px', background: '#fafbfc', borderRadius: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#333', marginBottom: 8 }}>国家构成</div>
                    {(() => {
                      const total = activeData.total_sales
                      const sortedMarkets = [...activeData.markets].sort((a: any, b: any) => b.sales - a.sales)
                      return sortedMarkets.map((m: any, i: number) => {
                        const pct = total > 0 ? (m.sales / total * 100) : 0
                        return (
                          <div key={i} style={{ marginBottom: 7 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#555', marginBottom: 2 }}>
                              <span>{m.market}</span>
                              <span>{pct.toFixed(1)}%</span>
                            </div>
                            <div style={{ height: 5, background: '#e8e8e8', borderRadius: 3, overflow: 'hidden' }}>
                              <div style={{ width: `${pct}%`, height: '100%', background: t.color }} />
                            </div>
                          </div>
                        )
                      })
                    })()}
                  </div>

                  {/* 型号参数 */}
                  {activeData.specs && (
                    <div style={{ flex: 1, padding: '12px 14px', background: '#f5f7fa', borderRadius: 8 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#333', marginBottom: 8 }}>型号参数</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '8px', fontSize: 12 }}>
                        {[
                          { label: '摄像头', value: activeData.specs.camera },
                          { label: '电池', value: activeData.specs.battery },
                          { label: 'CPU', value: activeData.specs.cpu },
                          { label: '内存', value: activeData.specs.memory_storage },
                          { label: '屏幕', value: activeData.specs.screen_size },
                          { label: '网络', value: activeData.specs.network },
                        ].map((item) => (
                          <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ color: '#999' }}>{item.label}</span>
                            <span style={{ color: '#333', fontWeight: 500 }}>{item.value || '-'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
