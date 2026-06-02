// 五个聚焦品牌的展示配置:配色 + 一句话简介。
// key 用小写,匹配时统一 toLowerCase()。
export interface BrandTheme {
  name: string
  color: string      // 主色
  gradient: string   // 卡片头部渐变
  intro: string      // 一句话简介
}

const THEMES: Record<string, BrandTheme> = {
  blackview: {
    name: 'Blackview',
    color: '#fa8c16',
    gradient: 'linear-gradient(135deg, #fa8c16 0%, #ffc069 100%)',
    intro: '三防户外手机与平板,主打耐用与高性价比',
  },
  ulefone: {
    name: 'Ulefone',
    color: '#52c41a',
    gradient: 'linear-gradient(135deg, #389e0d 0%, #95de64 100%)',
    intro: '坚固耐用智能机,夜视/对讲等差异化卖点',
  },
  cubot: {
    name: 'CUBOT',
    color: '#1677ff',
    gradient: 'linear-gradient(135deg, #1677ff 0%, #69b1ff 100%)',
    intro: '高性价比入门安卓机,主攻欧洲线上市场',
  },
  oukitel: {
    name: 'OUKITEL',
    color: '#f5222d',
    gradient: 'linear-gradient(135deg, #cf1322 0%, #ff7875 100%)',
    intro: '大电池三防机与户外电源,续航见长',
  },
  doogee: {
    name: 'DOOGEE',
    color: '#13c2c2',
    gradient: 'linear-gradient(135deg, #08979c 0%, #5cdbd3 100%)',
    intro: '三防与潮流外观并重,机型迭代快',
  },
}

const FALLBACK: BrandTheme = {
  name: '',
  color: '#8c8c8c',
  gradient: 'linear-gradient(135deg, #595959 0%, #bfbfbf 100%)',
  intro: '',
}

export function brandTheme(brand: string): BrandTheme {
  const t = THEMES[(brand || '').toLowerCase()]
  return t ?? { ...FALLBACK, name: brand }
}
