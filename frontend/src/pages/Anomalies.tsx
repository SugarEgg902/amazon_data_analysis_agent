import { Table, Tag, Button, Space, Select, Spin, Alert, message } from 'antd'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { api, unwrap } from '../api/client'
import { useMarket } from '../context/MarketContext'

const TYPE_LABELS: Record<string, string> = {
  sales_amount: '销售额', sales_volume: '销量', price: '价格',
  main_bsr: 'main BSR', sub_bsr: 'sub BSR',
}

// 计数类指标(销量/BSR排名)是整数,按四舍五入整数显示;
// 金额类(销售额/价格)保留两位小数。基线为7天均值,故计数类基线也四舍五入。
const INTEGER_TYPES = new Set(['sales_volume', 'main_bsr', 'sub_bsr'])

function fmtValue(type: string, v: any): string {
  if (v == null) return '-'
  const n = Number(v)
  return INTEGER_TYPES.has(type) ? Math.round(n).toLocaleString() : n.toFixed(2)
}

export default function Anomalies() {
  const { market } = useMarket()
  const qc = useQueryClient()
  const [type, setType] = useState<string>()

  const { data, isLoading, error } = useQuery({
    queryKey: ['anomalies', market, type],
    queryFn: () => unwrap<any>(api.get('/anomalies/latest', { params: { market, type } })),
  })

  const detect = useMutation({
    mutationFn: () => api.post('/anomalies/detect', {}),
    onSuccess: (r) => {
      message.success(`检测完成，发现 ${r.data?.data?.detected ?? 0} 条异常`)
      qc.invalidateQueries({ queryKey: ['anomalies'] })
    },
    onError: () => message.error('检测失败'),
  })

  // 默认检测:首次进入若还没有任何批次,自动运行一次,使默认视图带异常类型
  useEffect(() => {
    if (!isLoading && !data?.detected_at && !detect.isPending) {
      detect.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, data?.detected_at])

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (error) return <Alert type="error" message="加载失败" />

  const columns = [
    { title: '站点', dataIndex: 'market', width: 70 },
    { title: '品牌', dataIndex: 'brand', width: 120 },
    { title: 'ASIN', dataIndex: 'asin', width: 120 },
    { title: '类型', dataIndex: 'anomaly_type', width: 100,
      render: (t: string) => TYPE_LABELS[t] ?? t },
    { title: '方向', dataIndex: 'direction', width: 70,
      render: (d: string) => <Tag color={d === 'up' ? 'green' : 'red'}>{d === 'up' ? '↑ 升' : '↓ 降'}</Tag> },
    { title: '当前值', dataIndex: 'current_value',
      render: (v: any, row: any) => fmtValue(row.anomaly_type, v) },
    { title: '基线值', dataIndex: 'baseline_value',
      render: (v: any, row: any) => fmtValue(row.anomaly_type, v) },
    { title: '变化幅度', dataIndex: 'change_pct',
      render: (v: any) => <Tag color={Number(v) >= 0 ? 'green' : 'red'}>{Number(v).toFixed(1)}%</Tag> },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" loading={detect.isPending} onClick={() => detect.mutate()}>
          运行异常检测
        </Button>
        <Select allowClear placeholder="异常类型" style={{ width: 160 }} value={type}
          onChange={(v) => setType(v)}
          options={Object.entries(TYPE_LABELS).map(([k, v]) => ({ value: k, label: v }))} />
        {data?.detected_at && <span style={{ color: '#999' }}>批次: {data.detected_at}</span>}
      </Space>
      <Table rowKey="id" columns={columns as any} dataSource={data?.items ?? []}
        size="small" pagination={{ pageSize: 20 }} />
    </div>
  )
}
