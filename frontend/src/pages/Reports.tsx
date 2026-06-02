import { Card, Spin, Alert, Empty, Tag, Space, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { api, unwrap } from '../api/client'

export default function Reports() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['report-latest'],
    queryFn: () => unwrap<any>(api.get('/reports/latest')),
  })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (error) return <Alert type="error" message="加载失败" />
  if (!data) return <Empty description="暂无报告，等待定时任务生成" />

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
        </Space>
      }
    >
      <div className="markdown-body">
        <ReactMarkdown>{data.content || ''}</ReactMarkdown>
      </div>
    </Card>
  )
}
