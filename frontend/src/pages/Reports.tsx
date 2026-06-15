import { Card, Spin, Alert, Empty, Tag, Space, Typography, DatePicker } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import dayjs from 'dayjs'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, unwrap } from '../api/client'

export default function Reports() {
  const [selectedDate, setSelectedDate] = useState<string | undefined>(undefined)

  const { data, isLoading, error } = useQuery({
    queryKey: ['report', selectedDate],
    queryFn: () => unwrap<any>(api.get('/reports', { params: selectedDate ? { date: selectedDate } : {} })),
  })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (error) return <Alert type="error" message="加载失败" />
  if (!data) return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <DatePicker
          allowClear
          value={selectedDate ? dayjs(selectedDate) : undefined}
          onChange={(d) => setSelectedDate(d ? d.format('YYYY-MM-DD') : undefined)}
          placeholder="选择日期"
        />
      </Space>
      <Empty description="暂无报告" />
    </div>
  )

  if (data.status === 'failed') {
    return <Alert type="warning" message={`报告生成失败 (${data.report_date})`}
      description={data.error_message} />
  }

  return (
    <Card
      title={
        <Space>
          <Typography.Text strong>每日分析报告</Typography.Text>
          <Tag>{data.report_date}</Tag>
          <Tag color="blue">{data.model}</Tag>
          <DatePicker
            allowClear
            value={selectedDate ? dayjs(selectedDate) : undefined}
            onChange={(d) => setSelectedDate(d ? d.format('YYYY-MM-DD') : undefined)}
            placeholder="选择日期"
            size="small"
          />
        </Space>
      }
    >
      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.content || ''}</ReactMarkdown>
      </div>
    </Card>
  )
}
