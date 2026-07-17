import { Table, Tag, Button, Space, Select, Spin, Alert, message, DatePicker, InputNumber } from 'antd'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs, { Dayjs } from 'dayjs'
import { api, unwrap } from '../api/client'
import { useMarket } from '../context/MarketContext'

const { RangePicker } = DatePicker

const TYPE_LABELS: Record<string, string> = {
  sales_amount: '销售额', sales_volume: '销量', price: '价格',
  main_bsr: 'main BSR', sub_bsr: 'sub BSR',
}

// 计数类指标(销量/BSR排名)是整数,按四舍五入整数显示;
// 金额类(销售额/价格)保留两位小数。基线为所选日期范围的均值,故计数类基线也四舍五入。
const INTEGER_TYPES = new Set(['sales_volume', 'main_bsr', 'sub_bsr'])

function fmtValue(type: string, v: any): string {
  if (v == null) return '-'
  const n = Number(v)
  return INTEGER_TYPES.has(type) ? Math.round(n).toLocaleString() : n.toFixed(2)
}

export default function Anomalies() {
  const nav = useNavigate()
  const { market } = useMarket()
  const qc = useQueryClient()
  const [type, setType] = useState<string>()
  // 基线日期范围:默认最近 7 天(不含今天快照当天由后端保证)
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(7, 'day'), dayjs()])
  // 超过基线均值多少比例算异常(%)
  const [threshold, setThreshold] = useState<number>(30)

  const { data, isLoading, error } = useQuery({
    queryKey: ['anomalies', market, type],
    queryFn: () => unwrap<any>(api.get('/anomalies/latest', { params: { market, type } })),
  })

  const detect = useMutation({
    mutationFn: () => {
      const t = (threshold || 30) / 100
      return api.post('/anomalies/detect', {
        sales_amount_threshold: t, sales_volume_threshold: t, price_threshold: t,
        main_bsr_threshold: t, sub_bsr_threshold: t,
        start_date: range?.[0]?.format('YYYY-MM-DD'),
        end_date: range?.[1]?.format('YYYY-MM-DD'),
      })
    },
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
      <Space style={{ marginBottom: 16 }} wrap>
        <span>基线日期</span>
        <RangePicker value={range} allowClear={false}
          onChange={(v) => v && v[0] && v[1] && setRange([v[0], v[1]])}
          disabledDate={(d) => d && d > dayjs()} />
        <span>阈值</span>
        <InputNumber min={1} max={500} value={threshold} addonAfter="%"
          style={{ width: 110 }} onChange={(v) => setThreshold(v ?? 30)} />
        <Button type="primary" loading={detect.isPending} onClick={() => detect.mutate()}>
          运行异常检测
        </Button>
        <Select allowClear placeholder="异常类型" style={{ width: 160 }} value={type}
          onChange={(v) => setType(v)}
          options={Object.entries(TYPE_LABELS).map(([k, v]) => ({ value: k, label: v }))} />
        {data?.detected_at && <span style={{ color: '#999' }}>批次: {data.detected_at}</span>}
      </Space>
      <Table rowKey="id" columns={columns as any} dataSource={data?.items ?? []}
        size="small" pagination={{ pageSize: 20 }}
        onRow={(r: any) => ({ style: { cursor: 'pointer' },
          onClick: () => nav(`/products/${r.asin}?market=${r.market}`) })} />
    </div>
  )
}
