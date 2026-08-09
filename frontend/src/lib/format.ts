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
