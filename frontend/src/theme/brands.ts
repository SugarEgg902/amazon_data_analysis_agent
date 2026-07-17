// 储能电源赛道六个聚焦品牌的展示配置:配色 + 一句话简介。
// key 用小写,匹配时统一 toLowerCase()。OUKITEL 为自有品牌排第一。
// 后端可能返回原始品牌名(如 "ef ecoflow")或 canonical 展示名(如 "EcoFlow"),
// brandTheme() 通过 ALIASES 把两者都归一到同一主题 key。
export interface BrandTheme {
  name: string
  color: string      // 主色
  gradient: string   // 卡片头部渐变
  intro: string      // 一句话简介
}

const THEMES: Record<string, BrandTheme> = {
  oukitel: {
    name: 'OUKITEL',
    color: '#f5222d',
    gradient: 'linear-gradient(135deg, #cf1322 0%, #ff7875 100%)',
    intro: '自有品牌(本数据集以手机为主,储能数据待补)',
  },
  ecoflow: {
    name: 'EcoFlow',
    color: '#13c2c2',
    gradient: 'linear-gradient(135deg, #08979c 0%, #5cdbd3 100%)',
    intro: '便携储能电源行业头部,覆盖发电站/光伏板/配件',
  },
  bluetti: {
    name: 'Bluetti',
    color: '#1677ff',
    gradient: 'linear-gradient(135deg, #0958d9 0%, #69b1ff 100%)',
    intro: '大容量便携电源与家用储能,主打长续航与扩容',
  },
  jackery: {
    name: 'Jackery',
    color: '#fa8c16',
    gradient: 'linear-gradient(135deg, #d46b08 0%, #ffc069 100%)',
    intro: '户外便携电源与太阳能板,轻量便携见长',
  },
  vtoman: {
    name: 'VTOMAN',
    color: '#52c41a',
    gradient: 'linear-gradient(135deg, #389e0d 0%, #95de64 100%)',
    intro: '便携电源与汽车启动电源,主打应急启动',
  },
  anker: {
    name: 'Anker',
    color: '#722ed1',
    gradient: 'linear-gradient(135deg, #531dab 0%, #b37feb 100%)',
    intro: '综合电子品牌,含充电宝/充电器及部分便携电源',
  },
}

const FALLBACK: BrandTheme = {
  name: '',
  color: '#8c8c8c',
  gradient: 'linear-gradient(135deg, #595959 0%, #bfbfbf 100%)',
  intro: '',
}

// 后端原始品牌名 → 主题 key 的别名映射(处理带空格/前缀的历史命名)。
const ALIASES: Record<string, string> = {
  'ef ecoflow': 'ecoflow',
}

export function brandTheme(brand: string): BrandTheme {
  const key = (brand || '').toLowerCase()
  const t = THEMES[ALIASES[key] ?? key]
  return t ?? { ...FALLBACK, name: brand }
}
