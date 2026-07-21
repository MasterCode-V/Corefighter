const API = '/api/v1'

export type User = {
  id: string
  email: string
  full_name: string
  role: string
  store_id: string | null
}

export type Store = {
  id: string
  name: string
  code: string
  article_config?: Record<string, unknown>
}

export type Persona = {
  id: string
  name: string
  description: string
}

export type PurchaseImage = {
  id: string
  image_type: 'ARTICLE' | 'DETAIL'
  url: string
  filename: string
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
  status: string
  latest_similarity_score: number | null
  current_version: ArticleVersion | null
}

function authHeaders(token: string | null, json = true): HeadersInit {
  const h: Record<string, string> = {}
  if (json) h['Content-Type'] = 'application/json'
  if (token) h.Authorization = `Bearer ${token}`
  return h
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
      /* ignore */
    }
    throw new Error(detail)
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

export async function listPersonas(token: string) {
  const res = await fetch(`${API}/personas`, { headers: authHeaders(token) })
  return parse<Persona[]>(res)
}

export async function createPurchase(
  token: string,
  data: {
    store_id: string
    persona_id?: string | null
    purchase_date?: string
    purchase_method?: string
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
    headers: authHeaders(token),
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
    headers: authHeaders(token),
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
) {
  const form = new FormData()
  form.append('file', file)
  form.append('image_type', imageType)
  form.append('sort_order', String(sortOrder))
  const res = await fetch(`${API}/purchases/${purchaseId}/images`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  return parse<PurchaseImage>(res)
}

export async function analyzeImages(token: string, purchaseId: string) {
  const res = await fetch(`${API}/purchases/${purchaseId}/analyze`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  return parse<{ job_id: string; job_type: string; status: string }>(res)
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
    headers: authHeaders(token),
    body: JSON.stringify(data),
  })
  return parse<Article>(res)
}

export type RelatedPost = {
  id: number | null
  title: string
  link: string
  date: string
  thumbnail: string | null
  score: number | null
}

export type ArticleTemplate = {
  label?: string
  area?: string
  thanks_text?: string
  thanks_color?: string
  persona_intro?: string
  phone_general?: string
  phone_dispatch?: string
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
    headers: authHeaders(token),
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
  throw new Error('Job timed out')
}
