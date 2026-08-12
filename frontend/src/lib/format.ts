/** Articles run in two states only: 公開 (PUBLISHED) and 下書き (anything else). */
export function isPublished(status: string | null | undefined): boolean {
  return status === 'PUBLISHED'
}

export function statusLabel(status: string): string {
  return isPublished(status) ? '公開' : '下書き'
}

export function statusBadgeClass(status: string): string {
  return `cf-badge cf-badge--${isPublished(status) ? 'red' : 'gray'}`
}

/** Statuses offered in the 公開状態 filter. */
export const STATUS_FILTER_OPTIONS = ['PUBLISHED', 'DRAFT']

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

/** Map API / network / legacy English errors to Japanese for staff-facing alerts. */
export function explainWorkflowError(raw: unknown, fallback = 'エラーが発生しました'): string {
  const message =
    raw instanceof Error ? raw.message : typeof raw === 'string' ? raw : fallback
  let text = (message || '').trim()
  if (!text) return fallback

  // FastAPI validation array dumped as JSON
  if (text.startsWith('[{') && text.includes('"msg"')) {
    try {
      const items = JSON.parse(text) as Array<{ loc?: unknown[]; msg?: string }>
      const parts = items
        .map((i) => i.msg)
        .filter(Boolean)
        .join(' / ')
      if (parts) text = parts
    } catch {
      /* keep text */
    }
  }

  const rules: Array<[RegExp, string]> = [
    [/Job timed out/i, '処理がタイムアウトしました。時間をおいて再試行してください。'],
    [/Incorrect email or password/i, 'メールアドレスまたはパスワードが正しくありません'],
    [/Inactive user/i, 'このアカウントは無効です'],
    [/Could not validate credentials/i, '認証に失敗しました。再ログインしてください'],
    [/Insufficient permissions/i, 'この操作を行う権限がありません'],
    [/do not have access to this store/i, 'この店舗のデータにアクセスする権限がありません'],
    [/Email already registered/i, 'このメールアドレスは既に登録されています'],
    [/cannot delete the account you are signed in/i, 'ログイン中のアカウントは削除できません'],
    [/Product name is required/i, '記事を生成できません。理由：商品名が未入力です。'],
    [/No images uploaded|No images to analyze/i, '画像がありません。メイン画像を追加してください。'],
    [/Unsupported content type/i, '対応していない画像形式です（JPEG / PNG / WebP / GIF）。'],
    [/Image too large|413/i, '画像サイズが上限（15MB）を超えています。'],
    [/Persona not found|Unknown persona/i, '選択した AI ペルソナが見つかりません。'],
    [/Purchase not found/i, '買取データが見つかりません'],
    [/Article not found/i, '記事が見つかりません'],
    [/User not found/i, 'ユーザーが見つかりません'],
    [/Store not found/i, '店舗が見つかりません'],
    [/Job not found/i, 'ジョブが見つかりません'],
    [/WordPress site not found/i, 'WordPress接続設定が見つかりません'],
    [/No WordPress site configured/i, 'この店舗にWordPress接続が設定されていません'],
    [/No WordPress draft exists|No WordPress draft to publish/i, 'WordPress下書きがまだありません。'],
    [/Invalid refresh token/i, 'リフレッシュトークンが無効です。再ログインしてください。'],
    [/Not Found/i, '指定したデータが見つかりません。'],
    [/Unauthorized/i, '認証が必要です。再ログインしてください。'],
    [/Forbidden/i, 'この操作を行う権限がありません。'],
    [/Internal Server Error/i, 'サーバー内部エラーが発生しました。時間をおいて再試行してください。'],
    [/Bad Gateway|502/i, '外部サービス（WordPress等）との通信に失敗しました。'],
    [
      /Bad Request|リクエスト形式エラー/i,
      '処理できませんでした。ページを再読み込みしてから、もう一度お試しください。',
    ],
    [
      /Failed to fetch|NetworkError|Load failed|network/i,
      '通信に失敗しました。サーバー接続を確認してください。',
    ],
    [/field required/i, '必須項目が未入力です。'],
    [/value is not a valid uuid/i, 'IDの形式が正しくありません。'],
  ]

  for (const [re, msg] of rules) {
    if (re.test(text)) return msg
  }

  // If the message is still mostly ASCII English, wrap it.
  const asciiRatio = (text.match(/[\x00-\x7F]/g)?.join('').length || 0) / text.length
  if (asciiRatio > 0.85 && /[A-Za-z]{4,}/.test(text)) {
    return `エラー：${text}`
  }
  return text
}
