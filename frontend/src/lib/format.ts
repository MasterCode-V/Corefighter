export const ARTICLE_STATUS_LABELS: Record<string, string> = {
  DRAFT: '下書き',
  NEEDS_CORRECTION: '要修正',
  SIMILARITY_WARNING: '類似警告',
  WAITING_LIST: '公開待ち',
  WAITING_APPROVAL: '承認待ち',
  RETURNED: '差戻し',
  ON_HOLD: '保留',
  REJECTED: '却下',
  APPROVED: '承認済み',
  WORDPRESS_DRAFT: 'WP下書き',
  WORDPRESS_ERROR: 'WPエラー',
  PUBLISHED: '公開済み',
}

const STATUS_TONES: Record<string, 'red' | 'gray' | 'amber' | 'green'> = {
  PUBLISHED: 'red',
  WORDPRESS_ERROR: 'red',
  NEEDS_CORRECTION: 'amber',
  SIMILARITY_WARNING: 'amber',
  WAITING_APPROVAL: 'amber',
  RETURNED: 'amber',
  APPROVED: 'green',
  WORDPRESS_DRAFT: 'green',
}

export function statusLabel(status: string): string {
  return ARTICLE_STATUS_LABELS[status] || status
}

export function statusBadgeClass(status: string): string {
  return `cf-badge cf-badge--${STATUS_TONES[status] || 'gray'}`
}

/** Statuses offered in the 公開状態 filter, in workflow order. */
export const STATUS_FILTER_OPTIONS = [
  'DRAFT',
  'WAITING_LIST',
  'WAITING_APPROVAL',
  'APPROVED',
  'WORDPRESS_DRAFT',
  'PUBLISHED',
  'NEEDS_CORRECTION',
  'SIMILARITY_WARNING',
  'RETURNED',
  'ON_HOLD',
  'REJECTED',
  'WORDPRESS_ERROR',
]

export function formatJaDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

export function todayIso(): string {
  const d = new Date()
  const offset = d.getTimezoneOffset()
  return new Date(d.getTime() - offset * 60000).toISOString().slice(0, 10)
}

export const ROLE_LABELS: Record<string, string> = {
  ADMIN: '管理者',
  STORE_MANAGER: '店舗管理者',
  STORE_STAFF: '編集者',
}

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] || role
}

/** MinIO URLs are not reachable from the browser — route them via the API proxy. */
export function toProxy(html: string): string {
  return html.replace(
    /https?:\/\/[^"'\s]*?:9000\/corefighter-media\//g,
    '/api/v1/media/',
  )
}

export function proxyImageUrl(url: string | null | undefined): string {
  if (!url) return ''
  return url.replace(/https?:\/\/[^/]*?:9000\/corefighter-media\//, '/api/v1/media/')
}

const STORE_PREFIXES = ['パワフルトレードセンター', 'パワトレ', 'Powerful Trade Center']

/** Chips and card badges show 東苗穂店, not the full chain name. */
export function shortStoreName(name: string | null | undefined): string {
  const value = (name || '').trim()
  for (const prefix of STORE_PREFIXES) {
    if (value.startsWith(prefix)) {
      const rest = value.slice(prefix.length).trim()
      if (rest) return rest
    }
  }
  return value
}

/** Titles are stored with markup (e.g. a <br> before the 【…】 part). */
export function plainText(value: string | null | undefined): string {
  if (!value) return ''
  return value
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Map API / network errors to a Japanese reason the staff can act on. */
export function explainWorkflowError(raw: unknown, fallback: string): string {
  const message =
    raw instanceof Error ? raw.message : typeof raw === 'string' ? raw : fallback
  const text = (message || '').trim()
  if (!text) return fallback

  const rules: Array<[RegExp, string]> = [
    [
      /Product name is required/i,
      '記事を生成できません。理由：商品名が未入力です。画像解析結果を確認するか、商品名を手入力してください。',
    ],
    [
      /No images uploaded/i,
      '画像解析できません。理由：アップロード済みの画像がありません。メイン画像または詳細画像を追加してください。',
    ],
    [
      /Unsupported content type/i,
      `画像をアップロードできません。理由：対応していない形式です（JPEG / PNG / WebP / GIF のみ）。${text.includes(':') ? `（${text.split(':').slice(1).join(':').trim()}）` : ''}`,
    ],
    [
      /Image too large|413/i,
      '画像をアップロードできません。理由：ファイルサイズが上限（15MB）を超えています。',
    ],
    [
      /Persona not found/i,
      '保存できません。理由：選択した AI ペルソナが見つかりません。別のペルソナを選んでください。',
    ],
    [
      /Bad Request|リクエスト形式エラー/i,
      '処理できませんでした。理由：リクエスト形式エラーです。ページを再読み込みしてから、画像と入力内容を確認してもう一度お試しください。',
    ],
    [/Failed to fetch|NetworkError|network/i, '通信に失敗しました。理由：サーバーに接続できません。回線と VPS の起動状態を確認してください。'],
  ]

  for (const [re, msg] of rules) {
    if (re.test(text)) return msg
  }
  return text
}
