import type { PurchaseImage } from '../../api'

export type ProductRow = {
  key: string
  manufacturer: string
  product_name: string
  model_number: string
  condition: string
  quantity: string
  quantity_unit: string
  /** Picked in the browser, not uploaded yet. */
  files: File[]
  /** Already stored on the purchase. */
  images: PurchaseImage[]
}

let counter = 0

export function emptyProduct(): ProductRow {
  counter += 1
  return {
    key: `p${Date.now()}_${counter}`,
    manufacturer: '',
    product_name: '',
    model_number: '',
    condition: '',
    quantity: '1',
    quantity_unit: '点',
    files: [],
    images: [],
  }
}

export const PURCHASE_METHODS = ['店頭', '出張', '宅配'] as const

export const CONDITION_OPTIONS = [
  '未使用',
  '未使用に近い',
  '中古美品',
  '中古',
  '傷・汚れあり',
  'ジャンク',
] as const

export function areaIsManual(method: string) {
  return method === '出張' || method === '宅配'
}

/** 記事への追加指示（チェックで選べるネタ） */
export const TOPIC_OPTIONS = [
  {
    id: 'jichi',
    label: '昨今の自治ネタ',
    prompt:
      '本文のどこかで、札幌近辺の自治体・地域の身近な話題に軽く触れる（政治的な断定や批判は避け、親しみやすい雑談程度）。',
  },
  {
    id: 'kensetsu',
    label: '建築業界ネタ',
    prompt:
      '建築・建設業界の現場あるあるや業界ネタを1〜2文、自然に織り交ぜる（専門用語の羅列は避け、読者が楽しめる軽いトーン）。',
  },
  {
    id: 'tenki',
    label: '本日の天気',
    prompt:
      '本日の天気や季節感に軽く触れる。正確な予報データは無いので、季節・気温・空模様の雰囲気で自然に書く（断定しすぎない）。',
  },
  {
    id: 'lunch',
    label: '昼食メニュー（ランダム）',
    prompt:
      '昼食メニューをランダムに1つ挙げて、軽く雑談する（例：ラーメン、カレー、定食など）。商品紹介の邪魔にならない短さで。',
  },
  {
    id: 'yasumi',
    label: '明日休み（前日）',
    prompt:
      '「明日は休み」という前日の気分・現場の空気感に軽く触れる（休み明けの話題ではなく、前日としての雑談）。',
  },
  {
    id: 'dekigoto',
    label: '最近の出来事（雑談）',
    prompt:
      '最近のちょっとした出来事や日常雑談を1つ入れる。事実の捏造が過ぎないよう、一般的で無害なエピソードにする。',
  },
  {
    id: 'kenzai',
    label: '買い取った商品についての情報（どのように使われる建材か）',
    prompt:
      '買い取った商品が実際にどのように使われる建材・資材・道具か、用途や現場での使われ方をわかりやすく1〜2文で説明する（スペック羅列は禁止）。',
  },
] as const

export type TopicId = (typeof TOPIC_OPTIONS)[number]['id']

export function buildUserInstructions(
  flags: Record<string, boolean>,
  freeText: string,
): string | undefined {
  const selected = TOPIC_OPTIONS.filter((t) => flags[t.id])
  const parts: string[] = []
  if (selected.length) {
    parts.push('【本文に織り交ぜる追加ネタ（チェック済み）】')
    selected.forEach((t, i) => parts.push(`${i + 1}. ${t.label}: ${t.prompt}`))
    parts.push(
      '上記ネタはすべて本文に自然に含めること。ただし電話番号・フッター・価格は書かない。商品事実の捏造は禁止。',
    )
  }
  const free = freeText.trim()
  if (free) {
    parts.push('【スタッフ自由記入】')
    parts.push(free)
  }
  return parts.length ? parts.join('\n') : undefined
}
