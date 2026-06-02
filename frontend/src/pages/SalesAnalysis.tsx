import { Upload, Button, Card, Spin, Alert, Table, message, Space, Typography } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api, unwrap } from '../api/client'

export default function SalesAnalysis() {
  const qc = useQueryClient()
  const [current, setCurrent] = useState<any>(null)

  const { data: history } = useQuery({
    queryKey: ['sales-history'],
    queryFn: () => unwrap<any>(api.get('/sales-analysis/history')),
  })

  const upload = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return api.post('/sales-analysis/upload', fd)
    },
    onSuccess: (r) => {
      setCurrent(r.data?.data)
      message.success('分析完成')
      qc.invalidateQueries({ queryKey: ['sales-history'] })
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail || '分析失败'),
  })

  const openReport = async (id: number) => {
    const rep = await unwrap<any>(api.get(`/sales-analysis/reports/${id}`))
    setCurrent(rep)
  }

  const cols = [
    { title: '文件名', dataIndex: 'filename', ellipsis: true },
    { title: '行数', dataIndex: 'row_count', width: 90 },
    { title: '时间', dataIndex: 'report_date', width: 180 },
    { title: '状态', dataIndex: 'status', width: 90 },
    { title: '', width: 80,
      render: (_: any, r: any) => <a onClick={() => openReport(r.id)}>查看</a> },
  ]

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Upload
          accept=".csv,.xlsx,.xls"
          showUploadList={false}
          beforeUpload={(file) => { upload.mutate(file as File); return false }}
        >
          <Button icon={<UploadOutlined />} loading={upload.isPending} type="primary">
            上传销售文件 (CSV/Excel)
          </Button>
        </Upload>
        <Typography.Text type="secondary" style={{ marginLeft: 12 }}>
          自动识别数值/日期/分类列并生成分析报告
        </Typography.Text>
      </Card>

      {upload.isPending && <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />}

      {current && (
        <Card title={`分析报告 · ${current.filename ?? ''}`} style={{ marginBottom: 16 }}>
          {current.status === 'failed' ? (
            <Alert type="warning" message="分析失败" description={current.error_message} />
          ) : (
            <div className="markdown-body"><ReactMarkdown>{current.content || ''}</ReactMarkdown></div>
          )}
        </Card>
      )}

      <Card title="历史记录" size="small">
        <Table rowKey="id" columns={cols as any} dataSource={history?.items ?? []}
          size="small" pagination={{ pageSize: 10 }} />
      </Card>
    </div>
  )
}
