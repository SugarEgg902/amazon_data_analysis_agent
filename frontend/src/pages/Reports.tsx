import { Card, Spin, Alert, Empty, Tag, Space, Typography, DatePicker, Radio, Row, Col, Statistic } from 'antd'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useState } from 'react'
import dayjs from 'dayjs'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import ReactECharts from 'echarts-for-react'
import { api, unwrap } from '../api/client'
import TrendChart from '../components/TrendChart'
import PieChart from '../components/PieChart'
import { brandTheme } from '../theme/brands'

type Period = 'daily' | 'weekly' | 'monthly'

export default function Reports() {
  const [period, setPeriod] = useState<Period>('daily')
  const [selectedDate, setSelectedDate] = useState<string | undefined>(undefined)

  // 图表数据:日报=当天 / 周报=最近7天 / 月报=最近30天(截止基准日)
  const { data: summary, isLoading: sumLoading, error: sumError } = useQuery({
    queryKey: ['reportSummary', period, selectedDate],
    queryFn: async () => {
      const r = await api.get('/reports/summary', { params: { period, date: selectedDate } })
      const body: any = r.data
      // 形状不对时抛出原始响应,便于定位问题(HTML=被SPA兜底,说明后端是旧代码)
      if (body == null || typeof body !== 'object' || !('data' in body)) {
        const raw = typeof body === 'string' ? body : JSON.stringify(body)
        throw new Error(`接口返回异常: ${String(raw).slice(0, 300)}`)
      }
      return body.data
    },
    placeholderData: keepPreviousData,
  })

  // LLM 文字报告:仅日报
  const { data: report, isLoading: repLoading } = useQuery({
    queryKey: ['report', selectedDate],
    queryFn: () => unwrap<any>(api.get('/reports', { params: selectedDate ? { date: selectedDate } : {} })),
    enabled: period === 'daily',
    placeholderData: keepPreviousData,
  })

  if (sumLoading && !summary) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (sumError) {
    const e: any = sumError
    const status = e?.response?.status
    return <Alert type="error" message={`加载失败${status ? ` (HTTP ${status})` : ''}`}
      description={status === 404
        ? '后端没有 /api/reports/summary 接口——后端进程还在运行旧代码，请重启后端服务后刷新。'
        : (e?.response?.data?.detail || e?.message || String(e))} />
  }

  const controls = (
    <Space wrap style={{ marginBottom: 16 }}>
      <Radio.Group value={period} optionType="button" buttonStyle="solid"
        onChange={(e) => setPeriod(e.target.value)}
        options={[
          { value: 'daily', label: '日报' },
          { value: 'weekly', label: '周报' },
          { value: 'monthly', label: '月报' },
        ]} />
      <DatePicker allowClear placeholder="基准日期(默认最新)"
        value={selectedDate ? dayjs(selectedDate) : undefined}
        onChange={(d) => setSelectedDate(d ? d.format('YYYY-MM-DD') : undefined)}
        disabledDate={(d) => d && d > dayjs()} />
      {summary && (
        <Tag color="geekblue">
          {summary.start_date === summary.end_date
            ? summary.end_date : `${summary.start_date} ~ ${summary.end_date}`}
        </Tag>
      )}
    </Space>
  )

  if (!summary) return <div>{controls}<Empty description="暂无数据" /></div>

  const brands = summary.brands ?? []
  const dates = summary.dates ?? []
  const multiDay = dates.length > 1

  // 走势折线:按品牌一条线,颜色与全站品牌配色一致
  const revSeries: Record<string, (number | null)[]> = {}
  const salesSeries: Record<string, (number | null)[]> = {}
  const colors: Record<string, string> = {}
  brands.forEach((b: any) => {
    const t = brandTheme(b.brand)
    const name = t.name || b.brand
    revSeries[name] = b.revenue
    salesSeries[name] = b.sales
    colors[name] = t.color
  })

  // 品牌对比:营收/销量双轴柱状图(期间日均)
  const barOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['营收', '销量'] },
    grid: { top: 40, left: 80, right: 70, bottom: 60 },
    xAxis: { type: 'category', axisLabel: { rotate: 20 },
      data: brands.map((b: any) => brandTheme(b.brand).name || b.brand) },
    yAxis: [{ type: 'value', name: '营收($)' }, { type: 'value', name: '销量' }],
    series: [
      { name: '营收', type: 'bar',
        data: brands.map((b: any) => ({ value: b.avg_revenue,
          itemStyle: { color: brandTheme(b.brand).color } })) },
      { name: '销量', type: 'bar', yAxisIndex: 1, itemStyle: { color: '#bfbfbf' },
        data: brands.map((b: any) => b.avg_sales) },
    ],
  }

  const pie = (summary.categories ?? []).map((c: any) => ({
    name: c.sub_category, value: c.revenue,
  }))

  return (
    <div>
      {controls}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}><Card size="small">
          <Statistic title={multiDay ? '总营收(期间日均)' : '总营收'}
            value={summary.totals?.revenue} precision={0} prefix="$" /></Card></Col>
        <Col xs={12} md={6}><Card size="small">
          <Statistic title={multiDay ? '总销量(期间日均)' : '总销量'}
            value={summary.totals?.sales} /></Card></Col>
        <Col xs={12} md={6}><Card size="small">
          <Statistic title="品牌数" value={brands.length} /></Card></Col>
        <Col xs={12} md={6}><Card size="small">
          <Statistic title="数据天数" value={dates.length} /></Card></Col>
      </Row>
      <Row gutter={[16, 16]}>
        {multiDay && (
          <>
            <Col xs={24} lg={12}><Card size="small" title="品牌营收走势">
              <TrendChart dates={dates} series={revSeries as any} colors={colors} height={300} />
            </Card></Col>
            <Col xs={24} lg={12}><Card size="small" title="品牌销量走势">
              <TrendChart dates={dates} series={salesSeries as any} colors={colors} height={300} />
            </Card></Col>
          </>
        )}
        <Col xs={24} lg={12}><Card size="small" title={multiDay ? '品牌对比(期间日均)' : '品牌对比'}>
          <ReactECharts option={barOption} style={{ height: 300 }} notMerge />
        </Card></Col>
        <Col xs={24} lg={12}><Card size="small" title={multiDay ? '品类营收分布(期间日均)' : '品类营收分布'}>
          <PieChart data={pie} height={300} />
        </Card></Col>
      </Row>
      {period === 'daily' && (
        repLoading && !report
          ? <Spin style={{ display: 'block', margin: '40px auto' }} />
          : report?.status === 'failed'
            ? <Alert style={{ marginTop: 16 }} type="warning"
                message={`报告生成失败 (${report.report_date})`} description={report.error_message} />
            : report
              ? (
                <Card style={{ marginTop: 16 }} title={
                  <Space>
                    <Typography.Text strong>每日分析报告</Typography.Text>
                    <Tag>{report.report_date}</Tag>
                    <Tag color="blue">{report.model}</Tag>
                  </Space>
                }>
                  <div className="markdown-body">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.content || ''}</ReactMarkdown>
                  </div>
                </Card>
              )
              : <Card style={{ marginTop: 16 }}><Empty description="暂无文字报告" /></Card>
      )}
    </div>
  )
}
