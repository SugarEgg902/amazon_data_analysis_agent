import ReactECharts from 'echarts-for-react'

interface Props {
  data: { name: string; value: number }[]
  title?: string
  height?: number
}

export default function PieChart({ data, title = '', height = 320 }: Props) {
  const option = {
    title: title ? { text: title, left: 'center' } : undefined,
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', orient: 'vertical', right: 0, top: 'middle' },
    series: [{ type: 'pie', radius: ['40%', '65%'], center: ['40%', '55%'], data }],
  }
  return <ReactECharts option={option} style={{ height }} notMerge />
}
