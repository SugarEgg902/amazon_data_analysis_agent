import ReactECharts from 'echarts-for-react'

interface Props {
  dates: string[]
  series: Record<string, number[]>
  title?: string
  height?: number
  colors?: Record<string, string>  // 按 series 名指定线条颜色
}

export default function TrendChart({ dates, series, title = '', height = 320, colors }: Props) {
  const names = Object.keys(series)
  const option = {
    title: title ? { text: title } : undefined,
    tooltip: { trigger: 'axis' },
    legend: { data: names, type: 'scroll', top: title ? 30 : 0 },
    grid: { top: title ? 70 : 40, left: 60, right: 20, bottom: 40 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: names.map((name) => ({
      name, type: 'line', data: series[name], smooth: true,
      ...(colors?.[name] ? { itemStyle: { color: colors[name] },
                             lineStyle: { color: colors[name] } } : {}),
    })),
  }
  return <ReactECharts option={option} style={{ height }} notMerge />
}
