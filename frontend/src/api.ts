import { explainWorkflowError } from './lib/format'

const API = '/api/v1'

export type PersonaBrief = {
  id: string
  name: string
}

export type User = {
  id: string
  email: string
  full_name: string
  role: string
  store_id: string | null
  is_active?: boolean
  created_at?: string
  allowed_personas?: PersonaBrief[]
}

export type Store = {
  id: string
  name: string
  code: string
  sort_order?: number
  is_active?: boolean
  article_config?: Record<string, unknown>
}

export type PurchaseMethod = {
  id: string
  label: string
  sort_order: number
  is_active: boolean
  requires_area: boolean
  linked_store_id: string | null
  created_at?: string
}

export type Persona = {
  id: string
  name: string
  description: string
  tone?: string
  writing_style?: string
  system_prompt?: string
  store_id?: string | null
  is_active?: boolean
  created_at?: string
}

export type PurchaseImage = {
  id: string
  image_type: 'ARTICLE' | 'DETAIL'
  url: string
  filename: string
  sort_order?: number
  product_index?: number | null
}

export type Product = {
  id?: string
  sort_order?: number
  manufacturer?: string | null
  product_name?: string | null
  model_number?: string | null
  category?: string | null
  condition?: string | null
  characteristics?: string | null
  quantity?: number
  quantity_unit?: string
  price?: number | null
}

export type Purchase = {
  id: string
  store_id: string
  persona_id: string | null
  status: string
  purchase_date: string | null
  purchase_method: string | null
  purchase_area: string | null
  quantity: number
  quantity_unit: string
  manufacturer: string | null
  product_name: string | null
  model_number: string | null
  category: string | null
  condition: string | null
  characteristics: string | null
  price: number | null
  manual_notes: string | null
  user_instructions: string | null
  ai_extraction: Record<string, unknown>
  images: PurchaseImage[]
  products: Product[]
}

export type Job = {
  id: string
  job_type: string
  status: string
  error: string | null
  result: Record<string, unknown>
  attempts: number
}

export type ArticleVersion = {
  id: string
  version_no: number
  title: string
  introduction: string
  headings: Array<{ heading?: string; content?: string } | string>
  body: string
  rendered_html: string
  excerpt: string
  category_suggestion: string | null
  tag_suggestions: string[]
  validation_outcome: string | null
  validation_result: Record<string, unknown>
  similarity_score: number | null
}

export type Article = {
  id: string
  purchase_id: string
  store_id?: string
  status: string
  latest_similarity_score: number | null
  wordpress_post_id?: number | null
  published_url?: string | null
  review_note?: string | null
  related_posts?: RelatedPost[]
  current_version: ArticleVersion | null
}

/** Auth only — do not set Content-Type (important for GET/DELETE and bodyless POST). */
function authHeaders(token: string | null): HeadersInit {
  const h: Record<string, string> = {}
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

/** Auth + JSON Content-Type — use only when sending a JSON body. */
function jsonHeaders(token: string | null): HeadersInit {
  return { ...authHeaders(token), 'Content-Type': 'application/json' }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail
        ? typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail)
        : detail
    } catch {
      /* nginx / proxy HTML error pages have no JSON detail */
    }
    throw new Error(explainWorkflowError(detail, `エラー（HTTP ${res.status}）`))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password })
  const res = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  return parse<{ access_token: string; refresh_token: string }>(res)
}

export async function me(token: string) {
  const res = await fetch(`${API}/auth/me`, { headers: authHeaders(token) })
  return parse<User>(res)
}

export async function listStores(token: string) {
  const res = await fetch(`${API}/stores`, { headers: authHeaders(token) })
  return parse<Store[]>(res)
}

export async function createStore(
  token: string,
  data: {
    name: string
    code: string
    address?: string
    description?: string
    sort_order?: number
    article_config?: Record<string, unknown>
  },
) {
  const res = await fetch(`${API}/stores`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Store>(res)
}

export async function updateStore(
  token: string,
  id: string,
  data: {
    name?: string
    address?: string
    description?: string
    is_active?: boolean
    sort_order?: number
    article_config?: Record<string, unknown>
  },
) {
  const res = await fetch(`${API}/stores/${id}`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Store>(res)
}

export async function listPurchaseMethods(token: string) {
  const res = await fetch(`${API}/purchase-methods`, { headers: authHeaders(token) })
  return parse<PurchaseMethod[]>(res)
}

export async function createPurchaseMethod(
  token: string,
  data: {
    label: string
    sort_order?: number
    is_active?: boolean
    requires_area?: boolean
    linked_store_id?: string | null
  },
) {
  const res = await fetch(`${API}/purchase-methods`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<PurchaseMethod>(res)
}

export async function updatePurchaseMethod(
  token: string,
  id: string,
  data: {
    label?: string
    sort_order?: number
    is_active?: boolean
    requires_area?: boolean
    linked_store_id?: string | null
  },
) {
  const res = await fetch(`${API}/purchase-methods/${id}`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<PurchaseMethod>(res)
}

export async function deletePurchaseMethod(token: string, id: string) {
  const res = await fetch(`${API}/purchase-methods/${id}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  if (!res.ok) await parse(res)
}

export async function listPersonas(token: string, includeInactive = false) {
  const q = includeInactive ? '?include_inactive=true' : ''
  const res = await fetch(`${API}/personas${q}`, { headers: authHeaders(token) })
  return parse<Persona[]>(res)
}

export async function createPersona(
  token: string,
  data: { name: string; system_prompt?: string; description?: string; store_id?: string | null },
) {
  const res = await fetch(`${API}/personas`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Persona>(res)
}

export async function updatePersona(
  token: string,
  id: string,
  data: { name?: string; system_prompt?: string; description?: string; is_active?: boolean },
) {
  const res = await fetch(`${API}/personas/${id}`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Persona>(res)
}

export async function deletePersona(token: string, id: string) {
  const res = await fetch(`${API}/personas/${id}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return parse<void>(res)
}

export async function listUsers(token: string) {
  const res = await fetch(`${API}/users`, { headers: authHeaders(token) })
  return parse<User[]>(res)
}

export async function createUser(
  token: string,
  data: {
    email: string
    password: string
    full_name?: string
    role?: string
    store_id?: string | null
    allowed_persona_ids?: string[]
  },
) {
  const res = await fetch(`${API}/users`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<User>(res)
}

export async function updateUser(
  token: string,
  id: string,
  data: {
    full_name?: string
    role?: string
    store_id?: string | null
    is_active?: boolean
    password?: string
    allowed_persona_ids?: string[]
  },
) {
  const res = await fetch(`${API}/users/${id}`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<User>(res)
}

export async function deleteUser(token: string, id: string) {
  const res = await fetch(`${API}/users/${id}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return parse<void>(res)
}

export async function createPurchase(
  token: string,
  data: {
    store_id: string
    persona_id?: string | null
    purchase_date?: string
    purchase_method?: string
    purchase_area?: string
    quantity?: number
    quantity_unit?: string
    manufacturer?: string
    product_name?: string
    model_number?: string
    category?: string
    condition?: string
    characteristics?: string
    manual_notes?: string
    user_instructions?: string
    products?: Product[]
  },
) {
  const res = await fetch(`${API}/purchases`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Purchase>(res)
}

export async function getPurchase(token: string, id: string) {
  const res = await fetch(`${API}/purchases/${id}`, {
    headers: authHeaders(token),
  })
  return parse<Purchase>(res)
}

export async function updatePurchase(
  token: string,
  id: string,
  data: Record<string, unknown>,
) {
  const res = await fetch(`${API}/purchases/${id}`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Purchase>(res)
}

export async function uploadImage(
  token: string,
  purchaseId: string,
  file: File,
  imageType: 'ARTICLE' | 'DETAIL',
  sortOrder = 0,
  productIndex?: number,
) {
  // Some browsers send empty / octet-stream types; give the file a sane name+type.
  const safeName = file.name?.includes('.')
    ? file.name
    : `${file.name || 'image'}.jpg`
  const safeFile =
    file.type && file.type !== 'application/octet-stream'
      ? file
      : new File([file], safeName, { type: file.type || 'image/jpeg' })

  // Retry: nginx keep-alive desync occasionally returns a body-less 400
  // right after createPurchase; a fresh connection usually succeeds.
  let lastError: unknown
  for (let attempt = 1; attempt <= 3; attempt++) {
    const form = new FormData()
    form.append('file', safeFile)
    form.append('image_type', imageType)
    form.append('sort_order', String(sortOrder))
    if (productIndex !== undefined) form.append('product_index', String(productIndex))
    try {
      const res = await fetch(`${API}/purchases/${purchaseId}/images`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      })
      if (!res.ok && res.status === 400 && attempt < 3) {
        await res.text().catch(() => undefined)
        await new Promise((r) => setTimeout(r, 300 * attempt))
        continue
      }
      return parse<PurchaseImage>(res)
    } catch (err) {
      lastError = err
      if (attempt >= 3) break
      await new Promise((r) => setTimeout(r, 300 * attempt))
    }
  }
  throw lastError instanceof Error ? lastError : new Error('画像のアップロードに失敗しました')
}

export async function deletePurchaseImage(token: string, purchaseId: string, imageId: string) {
  const res = await fetch(`${API}/purchases/${purchaseId}/images/${imageId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return parse<void>(res)
}

export async function analyzeImages(token: string, purchaseId: string) {
  let lastError: unknown
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(`${API}/purchases/${purchaseId}/analyze`, {
        method: 'POST',
        headers: authHeaders(token),
      })
      if (!res.ok && res.status === 400 && attempt < 3) {
        await res.text().catch(() => undefined)
        await new Promise((r) => setTimeout(r, 250 * attempt))
        continue
      }
      return parse<{ job_id: string; job_type: string; status: string }>(res)
    } catch (err) {
      lastError = err
      if (attempt >= 3) break
      await new Promise((r) => setTimeout(r, 250 * attempt))
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new Error('画像解析の開始に失敗しました')
}

export async function generateArticle(
  token: string,
  purchaseId: string,
  userInstructions?: string,
) {
  const q = userInstructions
    ? `?user_instructions=${encodeURIComponent(userInstructions)}`
    : ''
  const res = await fetch(`${API}/purchases/${purchaseId}/generate${q}`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return parse<{ job_id: string; job_type: string; status: string }>(res)
}

export async function getJob(token: string, jobId: string) {
  const res = await fetch(`${API}/jobs/${jobId}`, {
    headers: authHeaders(token),
  })
  return parse<Job>(res)
}

export async function listArticles(token: string) {
  const res = await fetch(`${API}/articles?limit=20`, {
    headers: authHeaders(token),
  })
  return parse<Article[]>(res)
}

export async function getArticle(token: string, id: string) {
  const res = await fetch(`${API}/articles/${id}`, {
    headers: authHeaders(token),
  })
  return parse<Article>(res)
}

export type ArticleEdit = {
  title?: string
  body?: string
  rendered_html?: string
  excerpt?: string
  category_suggestion?: string
  tag_suggestions?: string[]
}

export async function editArticle(token: string, id: string, data: ArticleEdit) {
  const res = await fetch(`${API}/articles/${id}/edit`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Article>(res)
}

export type RelatedPost = {
  id: number | null
  article_id?: string | null
  title: string
  link: string
  date: string
  thumbnail: string | null
  score: number | null
}

export type WordpressTag = {
  id: number
  name: string
  count: number
}

export type ArticleTemplate = {
  label?: string
  area?: string
  thanks_text?: string
  thanks_color?: string
  persona_intro?: string
  phone_general?: string
  phone_dispatch?: string
  line_url?: string
  footer_html?: string
}

export async function getArticleTemplate(token: string, storeId: string) {
  const res = await fetch(`${API}/stores/${storeId}/article-template`, {
    headers: authHeaders(token),
  })
  return parse<{ resolved: Record<string, unknown>; overrides: Record<string, unknown> }>(res)
}

export async function updateArticleTemplate(
  token: string,
  storeId: string,
  data: ArticleTemplate,
) {
  const res = await fetch(`${API}/stores/${storeId}/article-template`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Store>(res)
}

export async function getRelatedPosts(token: string, articleId: string, limit = 4) {
  const res = await fetch(`${API}/wordpress/${articleId}/related?limit=${limit}`, {
    headers: authHeaders(token),
  })
  return parse<RelatedPost[]>(res)
}

export async function searchRelatedCandidates(
  token: string,
  articleId: string,
  q = '',
  limit = 20,
) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (q.trim()) params.set('q', q.trim())
  const res = await fetch(`${API}/articles/${articleId}/related-candidates?${params}`, {
    headers: authHeaders(token),
  })
  return parse<RelatedPost[]>(res)
}

export async function updateRelatedPosts(token: string, articleId: string, items: RelatedPost[]) {
  const res = await fetch(`${API}/articles/${articleId}/related`, {
    method: 'PUT',
    headers: jsonHeaders(token),
    body: JSON.stringify({
      items: items.slice(0, 4).map((p) => ({
        id: p.id,
        article_id: p.article_id || null,
        title: p.title,
        link: p.link,
        date: p.date,
        thumbnail: p.thumbnail,
        score: p.score,
      })),
    }),
  })
  return parse<Article>(res)
}

export async function listWordpressTags(
  token: string,
  opts: { search?: string; storeId?: string; limit?: number } = {},
) {
  const q = new URLSearchParams()
  if (opts.search) q.set('search', opts.search)
  if (opts.storeId) q.set('store_id', opts.storeId)
  if (opts.limit) q.set('limit', String(opts.limit))
  const qs = q.toString()
  const res = await fetch(`${API}/wordpress/tags${qs ? `?${qs}` : ''}`, {
    headers: authHeaders(token),
  })
  return parse<WordpressTag[]>(res)
}

export async function listArticlesByStatus(token: string, status?: string, limit = 50) {
  const q = status ? `?status=${encodeURIComponent(status)}&limit=${limit}` : `?limit=${limit}`
  const res = await fetch(`${API}/articles${q}`, { headers: authHeaders(token) })
  return parse<Article[]>(res)
}

export async function publishArticle(token: string, articleId: string) {
  const res = await fetch(`${API}/wordpress/${articleId}/publish`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return parse<{ job_id: string; job_type: string; status: string }>(res)
}

export async function listWordpressCategories(token: string, productOnly = true) {
  const q = productOnly ? '?product_only=true' : '?product_only=false'
  const res = await fetch(`${API}/wordpress/categories${q}`, { headers: authHeaders(token) })
  return parse<Array<{ id: number; name: string; is_product: boolean }>>(res)
}

export async function createWordpressDraft(token: string, articleId: string) {
  const res = await fetch(`${API}/wordpress/${articleId}/draft`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return parse<{ job_id: string; job_type: string; status: string }>(res)
}

export async function retryWordpress(
  token: string,
  articleId: string,
  jobType = 'WORDPRESS_PUBLISH',
) {
  const res = await fetch(
    `${API}/wordpress/${articleId}/retry?job_type=${encodeURIComponent(jobType)}`,
    { method: 'POST', headers: authHeaders(token) },
  )
  return parse<{ job_id: string; job_type: string; status: string }>(res)
}

export async function syncWordpressCorpus(token: string) {
  const res = await fetch(`${API}/wordpress/sync`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return parse<{ job_id: string; job_type: string; status: string }>(res)
}

export async function regenerateArticle(
  token: string,
  articleId: string,
  instruction?: string,
) {
  const res = await fetch(`${API}/articles/${articleId}/regenerate`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify({ scope: 'FULL', instruction: instruction || null }),
  })
  return parse<{ job_id: string; job_type: string; status: string }>(res)
}

export type DashboardSummary = {
  articles_by_status: Record<string, number>
  purchases_by_status: Record<string, number>
  jobs_by_status: Record<string, number>
  published: number
  draft: number
  failed_jobs: number
}

export async function getDashboardSummary(token: string) {
  const res = await fetch(`${API}/dashboard/summary`, { headers: authHeaders(token) })
  return parse<DashboardSummary>(res)
}

export async function getDashboardLogs(token: string, limit = 40) {
  const res = await fetch(`${API}/dashboard/logs?limit=${limit}`, {
    headers: authHeaders(token),
  })
  return parse<
    Array<{
      id: string
      level: string
      category: string
      message: string
      created_at: string
    }>
  >(res)
}

export async function getRecentJobs(token: string, limit = 20) {
  const res = await fetch(`${API}/dashboard/recent-jobs?limit=${limit}`, {
    headers: authHeaders(token),
  })
  return parse<Job[]>(res)
}

export async function listPurchases(token: string, limit = 50) {
  const res = await fetch(`${API}/purchases?limit=${limit}`, { headers: authHeaders(token) })
  return parse<Purchase[]>(res)
}

export async function searchArticles(
  token: string,
  opts: { status?: string; search?: string; storeId?: string; limit?: number } = {},
) {
  const q = new URLSearchParams()
  if (opts.status) q.set('status', opts.status)
  if (opts.search) q.set('search', opts.search)
  if (opts.storeId) q.set('store_id', opts.storeId)
  q.set('limit', String(opts.limit ?? 50))
  const res = await fetch(`${API}/articles?${q}`, { headers: authHeaders(token) })
  return parse<Article[]>(res)
}

export type ArticleListItem = {
  id: string
  purchase_id: string
  store_id: string
  store_name: string
  status: string
  title: string
  thumbnail_url: string | null
  manufacturer: string
  product_name: string
  model_number: string
  product_count: number
  published_url: string | null
  wordpress_post_id: number | null
  created_at: string
  updated_at: string
}

export type ArticleListPage = {
  total: number
  limit: number
  offset: number
  items: ArticleListItem[]
}

export type StoreArticleStats = {
  store_id: string
  store_name: string
  published: number
  draft: number
  total: number
}

export type BrowseParams = {
  status?: string
  storeId?: string
  search?: string
  dateFrom?: string
  dateTo?: string
  order?: string
  limit?: number
  offset?: number
}

export async function browseArticles(token: string, params: BrowseParams = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.storeId) q.set('store_id', params.storeId)
  if (params.search) q.set('search', params.search)
  if (params.dateFrom) q.set('date_from', params.dateFrom)
  if (params.dateTo) q.set('date_to', params.dateTo)
  q.set('order', params.order || 'updated_desc')
  q.set('limit', String(params.limit ?? 30))
  q.set('offset', String(params.offset ?? 0))
  const res = await fetch(`${API}/articles/browse?${q}`, { headers: authHeaders(token) })
  return parse<ArticleListPage>(res)
}

export async function getArticleStats(token: string) {
  const res = await fetch(`${API}/articles/stats`, { headers: authHeaders(token) })
  return parse<StoreArticleStats[]>(res)
}

export async function deleteArticle(token: string, id: string) {
  const res = await fetch(`${API}/articles/${id}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return parse<void>(res)
}

export async function triggerSimilarityCheck(token: string, articleId: string) {
  const res = await fetch(`${API}/articles/${articleId}/similarity-check`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return parse<{ job_id: string; job_type: string; status: string }>(res)
}

export async function updateWordpressSite(
  token: string,
  siteId: string,
  data: {
    name?: string
    base_url?: string
    username?: string
    app_password?: string
    default_category_id?: number | null
    default_author_id?: number | null
    is_active?: boolean
  },
) {
  const res = await fetch(`${API}/stores/wordpress/${siteId}`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Record<string, unknown>>(res)
}

export async function createWordpressSite(
  token: string,
  storeId: string,
  data: {
    name?: string
    base_url: string
    username: string
    app_password: string
    default_category_id?: number | null
    default_author_id?: number | null
  },
) {
  const res = await fetch(`${API}/stores/${storeId}/wordpress`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Record<string, unknown>>(res)
}

export async function listWordpressSites(token: string, storeId: string) {
  const res = await fetch(`${API}/stores/${storeId}/wordpress`, {
    headers: authHeaders(token),
  })
  return parse<
    Array<{
      id: string
      store_id: string
      name: string
      base_url: string
      username: string
      is_active: boolean
    }>
  >(res)
}

export async function pollJob(
  token: string,
  jobId: string,
  onTick?: (job: Job) => void,
  timeoutMs = 180_000,
): Promise<Job> {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const job = await getJob(token, jobId)
    onTick?.(job)
    if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(job.status)) return job
    await new Promise((r) => setTimeout(r, 1500))
  }
  throw new Error('処理がタイムアウトしました。時間をおいて再試行してください。')
}
