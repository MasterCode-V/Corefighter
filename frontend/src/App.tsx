import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  analyzeImages,
  createPurchase,
  editArticle,
  generateArticle,
  getArticle,
  getArticleTemplate,
  getPurchase,
  getRelatedPosts,
  listArticles,
  listPersonas,
  listStores,
  login,
  me,
  pollJob,
  updateArticleTemplate,
  updatePurchase,
  uploadImage,
} from './api'
import type { Article, Persona, Product, Purchase, RelatedPost, Store, User } from './api'

function toProxy(html: string) {
  return html.replace(
    /https?:\/\/(?:localhost|127\.0\.0\.1):9000\/corefighter-media\//g,
    '/api/v1/media/',
  )
}

type Step = 'input' | 'analyze' | 'generate' | 'done'

const TOKEN_KEY = 'cf_token'

function pillClass(status: string) {
  if (['COMPLETED', 'ANALYZED', 'ARTICLE_READY', 'WAITING_LIST', 'PUBLISHED'].includes(status))
    return 'pill ok'
  if (['FAILED', 'WORDPRESS_ERROR', 'NEEDS_CORRECTION'].includes(status)) return 'pill err'
  if (status.includes('RUNNING') || status.includes('QUEUED') || status === 'RETRYING')
    return 'pill warn'
  return 'pill'
}

function imageTypeLabel(type: 'ARTICLE' | 'DETAIL') {
  return type === 'ARTICLE' ? '記事画像' : '詳細画像'
}

function todayIso() {
  const d = new Date()
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10)
}

// 買取方法が店頭以外（出張・宅配）のときは店舗を「買取場所」として扱わない。
function locationDisabled(method: string) {
  return method !== '店頭'
}

type ProductRow = {
  manufacturer: string
  product_name: string
  model_number: string
  condition: string
  quantity: string
  quantity_unit: string
}

function emptyProduct(): ProductRow {
  return {
    manufacturer: '',
    product_name: '',
    model_number: '',
    condition: '',
    quantity: '1',
    quantity_unit: '点',
  }
}

function productsFromPurchase(p: Purchase): ProductRow[] {
  const rows = p.products && p.products.length ? p.products : null
  if (rows) {
    return rows.map((x) => ({
      manufacturer: x.manufacturer || '',
      product_name: x.product_name || '',
      model_number: x.model_number || '',
      condition: x.condition || '',
      quantity: String(x.quantity ?? 1),
      quantity_unit: x.quantity_unit || '点',
    }))
  }
  return [
    {
      manufacturer: p.manufacturer || '',
      product_name: p.product_name || '',
      model_number: p.model_number || '',
      condition: p.condition || '',
      quantity: String(p.quantity ?? 1),
      quantity_unit: p.quantity_unit || '点',
    },
  ]
}

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<User | null>(null)
  const [email, setEmail] = useState('admin@corefighter.local')
  const [password, setPassword] = useState('admin12345')
  const [stores, setStores] = useState<Store[]>([])
  const [personas, setPersonas] = useState<Persona[]>([])
  const [storeId, setStoreId] = useState('')
  const [personaId, setPersonaId] = useState('')
  const [articleFiles, setArticleFiles] = useState<File[]>([])
  const [detailFiles, setDetailFiles] = useState<File[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [form, setForm] = useState({
    purchase_date: todayIso(),
    purchase_method: '店頭',
    category: '',
    characteristics: '',
    manual_notes: '',
    user_instructions: '',
  })
  const [products, setProducts] = useState<ProductRow[]>([emptyProduct()])
  const [purchase, setPurchase] = useState<Purchase | null>(null)
  const [article, setArticle] = useState<Article | null>(null)
  const [jobStatus, setJobStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [step, setStep] = useState<Step>('input')
  const [log, setLog] = useState<string[]>([])
  const [editing, setEditing] = useState(false)
  const [advanced, setAdvanced] = useState(false)
  const [related, setRelated] = useState<RelatedPost[] | null>(null)
  const [relatedMsg, setRelatedMsg] = useState('')
  const [edit, setEdit] = useState({
    title: '',
    body: '',
    rendered_html: '',
    excerpt: '',
    tags: '',
  })
  const [tplOpen, setTplOpen] = useState(false)
  const [tpl, setTpl] = useState({
    thanks_text: '',
    phone_general: '',
    phone_dispatch: '',
    footer_html: '',
  })

  function updateProduct(idx: number, patch: Partial<ProductRow>) {
    setProducts((prev) => prev.map((p, i) => (i === idx ? { ...p, ...patch } : p)))
  }
  function addProduct() {
    setProducts((prev) => [...prev, emptyProduct()])
  }
  function removeProduct(idx: number) {
    setProducts((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== idx)))
  }

  const previews = useMemo(() => {
    const all = [
      ...articleFiles.map((f) => ({ file: f, type: 'ARTICLE' as const })),
      ...detailFiles.map((f) => ({ file: f, type: 'DETAIL' as const })),
    ]
    return all.map((item) => ({
      ...item,
      url: URL.createObjectURL(item.file),
    }))
  }, [articleFiles, detailFiles])

  useEffect(() => {
    return () => previews.forEach((p) => URL.revokeObjectURL(p.url))
  }, [previews])

  useEffect(() => {
    if (!token) return
    ;(async () => {
      try {
        const u = await me(token)
        setUser(u)
        const [s, p] = await Promise.all([listStores(token), listPersonas(token)])
        setStores(s)
        setPersonas(p)
        if (s[0]) setStoreId(u.store_id || s[0].id)
        if (p[0]) setPersonaId(p[0].id)
      } catch (e) {
        localStorage.removeItem(TOKEN_KEY)
        setToken(null)
        setError(e instanceof Error ? e.message : 'セッションの有効期限が切れました')
      }
    })()
  }, [token])

  function pushLog(msg: string) {
    setLog((prev) => [`${new Date().toLocaleTimeString()}  ${msg}`, ...prev].slice(0, 40))
  }

  function productsPayload(): Product[] {
    return products
      .map((p, i) => ({
        sort_order: i,
        manufacturer: p.manufacturer.trim() || undefined,
        product_name: p.product_name.trim() || undefined,
        model_number: p.model_number.trim() || undefined,
        condition: p.condition.trim() || undefined,
        quantity: Number(p.quantity) > 0 ? Number(p.quantity) : 1,
        quantity_unit: p.quantity_unit.trim() || '点',
      }))
      .filter((p) => p.manufacturer || p.product_name || p.model_number)
  }

  function formPayload() {
    const text = Object.fromEntries(
      Object.entries(form).map(([k, v]) => [k, v.trim() || undefined]),
    )
    const prods = productsPayload()
    return { ...text, products: prods.length ? prods : undefined }
  }

  async function onLogin(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const t = await login(email, password)
      localStorage.setItem(TOKEN_KEY, t.access_token)
      setToken(t.access_token)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ログインに失敗しました')
    } finally {
      setBusy(false)
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
    setPurchase(null)
    setArticle(null)
    setStep('input')
  }

  function onPickFiles(files: FileList | null, kind: 'ARTICLE' | 'DETAIL') {
    if (!files?.length) return
    const list = Array.from(files).filter((f) => f.type.startsWith('image/'))
    if (kind === 'ARTICLE') setArticleFiles((prev) => [...prev, ...list].slice(0, 3))
    else setDetailFiles((prev) => [...prev, ...list].slice(0, 8))
  }

  async function runAnalyze() {
    if (!token || !purchase) return
    setError('')
    setBusy(true)
    setJobStatus('QUEUED')
    try {
      pushLog('画像解析ジョブを開始…')
      const { job_id } = await analyzeImages(token, purchase.id)
      const job = await pollJob(token, job_id, (j) => {
        setJobStatus(j.status)
        pushLog(`解析ジョブ: ${j.status}`)
      })
      if (job.status === 'FAILED') throw new Error(job.error || '画像解析に失敗しました')
      const fresh = await getPurchase(token, purchase.id)
      setPurchase(fresh)
      setProducts(productsFromPurchase(fresh))
      setForm((f) => ({
        ...f,
        category: fresh.category || f.category,
        characteristics: fresh.characteristics || f.characteristics,
      }))
      setStep('generate')
      const many = fresh.products && fresh.products.length > 1
      pushLog(
        many
          ? `解析完了 — ${fresh.products.length}商品を検出。内容を確認してください`
          : '解析完了 — 内容を確認してから記事を生成してください',
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : '画像解析に失敗しました')
      pushLog(`解析エラー: ${err instanceof Error ? err.message : err}`)
    } finally {
      setBusy(false)
    }
  }

  async function saveCorrections() {
    if (!token || !purchase) return
    setBusy(true)
    try {
      const fresh = await updatePurchase(token, purchase.id, {
        ...formPayload(),
        persona_id: personaId || null,
      })
      setPurchase(fresh)
      pushLog('商品情報を保存しました')
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存に失敗しました')
    } finally {
      setBusy(false)
    }
  }

  async function runGenerate() {
    if (!token || !purchase) return
    setError('')
    setBusy(true)
    setJobStatus('QUEUED')
    try {
      await saveCorrections()
      pushLog('記事生成ジョブを開始…')
      const { job_id } = await generateArticle(
        token,
        purchase.id,
        form.user_instructions || undefined,
      )
      const job = await pollJob(token, job_id, (j) => {
        setJobStatus(j.status)
        pushLog(`生成ジョブ: ${j.status}`)
      })
      if (job.status === 'FAILED') throw new Error(job.error || '記事生成に失敗しました')

      pushLog('記事と類似率チェックを待機中…')
      let art: Article | null = null
      for (let i = 0; i < 40; i++) {
        const arts = await listArticles(token)
        art = arts.find((a) => a.purchase_id === purchase.id) || null
        if (art?.current_version?.title) {
          art = await getArticle(token, art.id)
          const stillChecking =
            art.status === 'DRAFT' && !art.latest_similarity_score && i < 20
          if (!stillChecking) break
        }
        await new Promise((r) => setTimeout(r, 1500))
      }
      if (!art) throw new Error('生成後の記事が見つかりません')
      setArticle(art)
      setPurchase(await getPurchase(token, purchase.id))
      setStep('done')
      pushLog(`記事の準備完了 — ステータス ${art.status}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '記事生成に失敗しました')
      pushLog(`生成エラー: ${err instanceof Error ? err.message : err}`)
    } finally {
      setBusy(false)
    }
  }

  async function uploadAndAnalyze() {
    if (!token) return
    // Retry path: purchase + images already exist, just re-run analysis.
    if (purchase) {
      await runAnalyze()
      return
    }
    if (!storeId) {
      setError('買取場所を選択してください')
      return
    }
    if (!articleFiles.length && !detailFiles.length) {
      setError('画像を1枚以上追加してください')
      return
    }
    setError('')
    setBusy(true)
    setJobStatus('QUEUED')
    try {
      pushLog('買取データを作成中…')
      const created = await createPurchase(token, {
        store_id: storeId,
        persona_id: personaId || null,
        ...formPayload(),
      })
      setPurchase(created)
      pushLog(`買取 ${created.id.slice(0, 8)}… を作成`)
      let order = 0
      for (const file of articleFiles) {
        await uploadImage(token, created.id, file, 'ARTICLE', order++)
        pushLog(`記事画像をアップロード: ${file.name}`)
      }
      for (const file of detailFiles) {
        await uploadImage(token, created.id, file, 'DETAIL', order++)
        pushLog(`詳細画像をアップロード: ${file.name}`)
      }
      setStep('analyze')
      pushLog('画像解析ジョブを開始…')
      const { job_id } = await analyzeImages(token, created.id)
      const job = await pollJob(token, job_id, (j) => {
        setJobStatus(j.status)
        pushLog(`解析ジョブ: ${j.status}`)
      })
      if (job.status === 'FAILED') throw new Error(job.error || '画像解析に失敗しました')
      const fresh = await getPurchase(token, created.id)
      setPurchase(fresh)
      setProducts(productsFromPurchase(fresh))
      setForm((f) => ({
        ...f,
        category: fresh.category || f.category,
        characteristics: fresh.characteristics || f.characteristics,
      }))
      setStep('generate')
      const many = fresh.products && fresh.products.length > 1
      pushLog(
        many
          ? `解析完了 — ${fresh.products.length}商品を検出。内容を確認してください`
          : '解析完了 — 内容を確認して記事を生成してください',
      )
    } catch (err) {
      setStep('input')
      setError(err instanceof Error ? err.message : '処理に失敗しました')
      pushLog(`エラー: ${err instanceof Error ? err.message : err}`)
    } finally {
      setBusy(false)
    }
  }

  function startEditing() {
    const v = article?.current_version
    if (!v) return
    setEdit({
      title: v.title || '',
      body: v.body || '',
      rendered_html: v.rendered_html || '',
      excerpt: v.excerpt || '',
      tags: (v.tag_suggestions || []).join(', '),
    })
    setAdvanced(false)
    setEditing(true)
  }

  async function saveEdit() {
    if (!token || !article) return
    setError('')
    setBusy(true)
    try {
      const payload = advanced
        ? {
            title: edit.title,
            rendered_html: edit.rendered_html,
            excerpt: edit.excerpt,
            tag_suggestions: edit.tags
              .split(',')
              .map((t) => t.trim())
              .filter(Boolean),
          }
        : {
            title: edit.title,
            body: edit.body,
            excerpt: edit.excerpt,
            tag_suggestions: edit.tags
              .split(',')
              .map((t) => t.trim())
              .filter(Boolean),
          }
      const updated = await editArticle(token, article.id, payload)
      const fresh = await getArticle(token, updated.id)
      setArticle(fresh)
      setEditing(false)
      pushLog(`記事を編集しました — 新バージョン v${fresh.current_version?.version_no}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '編集の保存に失敗しました')
    } finally {
      setBusy(false)
    }
  }

  async function loadRelated() {
    if (!token || !article) return
    setRelatedMsg('')
    setRelated(null)
    try {
      const items = await getRelatedPosts(token, article.id, 4)
      setRelated(items)
      if (!items.length) setRelatedMsg('YARPPから関連記事が返りませんでした。')
    } catch (err) {
      setRelatedMsg(err instanceof Error ? err.message : '関連記事の取得に失敗しました')
    }
  }

  async function openTemplateEditor() {
    if (!token || !storeId) return
    try {
      const { resolved } = await getArticleTemplate(token, storeId)
      setTpl({
        thanks_text: String(resolved.thanks_text ?? ''),
        phone_general: String(resolved.phone_general ?? ''),
        phone_dispatch: String(resolved.phone_dispatch ?? ''),
        footer_html: String(resolved.footer_html ?? ''),
      })
      setTplOpen(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'テンプレートの取得に失敗しました')
    }
  }

  async function saveTemplate() {
    if (!token || !storeId) return
    setBusy(true)
    try {
      await updateArticleTemplate(token, storeId, tpl)
      pushLog('店舗テンプレート（フッター等）を保存しました')
      setTplOpen(false)
      // Re-fetch stores so subsequent generations pick up the new template.
      setStores(await listStores(token))
      // Rebuild the current article so the preview reflects the new footer.
      if (article) {
        const updated = await editArticle(token, article.id, {
          body: article.current_version?.body ?? '',
        })
        setArticle(await getArticle(token, updated.id))
        pushLog('現在の記事を新テンプレートで再組み立てしました')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'テンプレートの保存に失敗しました')
    } finally {
      setBusy(false)
    }
  }

  function resetFlow() {
    setPurchase(null)
    setArticle(null)
    setArticleFiles([])
    setDetailFiles([])
    setJobStatus('')
    setEditing(false)
    setRelated(null)
    setRelatedMsg('')
    setStep('input')
    setForm({
      purchase_date: todayIso(),
      purchase_method: '店頭',
      category: '',
      characteristics: '',
      manual_notes: '',
      user_instructions: '',
    })
    setProducts([emptyProduct()])
    pushLog('リセット — 新しい買取テストを開始')
  }

  if (!token || !user) {
    return (
      <div className="login-wrap">
        <form className="panel login-card" onSubmit={onLogin}>
          <div className="brand" style={{ marginBottom: 18 }}>
            <strong>CORE FIGHTER</strong>
            <span>テストコンソール — 画像からAI記事下書きまで</span>
          </div>
          {error && <div className="error-banner">{error}</div>}
          <div className="field">
            <label>メールアドレス</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
          </div>
          <div className="field">
            <label>パスワード</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <button className="btn btn-primary" disabled={busy} type="submit">
            {busy ? 'ログイン中…' : 'ログイン'}
          </button>
        </form>
      </div>
    )
  }

  const version = article?.current_version

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <strong>CORE FIGHTER</strong>
          <span>テストUI — 画像アップロード・入力・AI生成・結果確認</span>
        </div>
        <div className="user-chip">
          <span>
            {user.full_name || user.email} · {user.role}
          </span>
          <button className="btn btn-ghost" type="button" onClick={logout}>
            ログアウト
          </button>
        </div>
      </header>

      <div className="steps">
        {(
          [
            ['input', '1. 入力'],
            ['analyze', '2. 画像解析'],
            ['generate', '3. 記事生成'],
            ['done', '4. 結果'],
          ] as const
        ).map(([id, label]) => {
          const order = ['input', 'analyze', 'generate', 'done']
          const active = step === id
          const done = order.indexOf(step) > order.indexOf(id)
          return (
            <span key={id} className={`step${active ? ' active' : ''}${done ? ' done' : ''}`}>
              {label}
            </span>
          )
        })}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="grid-2">
        <section className="panel">
          <h2>入力</h2>
          <p className="lead">
            {step === 'input'
              ? '① 画像を追加 → ②「画像を解析」を押すと、作成・アップロード・解析をまとめて実行します。商品情報は空欄でも解析で補完されます。'
              : '解析結果を確認・修正し、必要に応じて追加情報を入力してから「記事を生成」を押してください。'}
          </p>

          <div className="field">
            <label>AIペルソナ</label>
            <select
              value={personaId}
              onChange={(e) => setPersonaId(e.target.value)}
              disabled={step === 'done'}
            >
              <option value="">— なし —</option>
              {personas.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>日付</label>
            <input
              type="date"
              value={form.purchase_date}
              onChange={(e) => setForm({ ...form, purchase_date: e.target.value })}
            />
          </div>

          <div className="field">
            <label>買取方法</label>
            <select
              value={form.purchase_method}
              onChange={(e) => setForm({ ...form, purchase_method: e.target.value })}
            >
              <option value="店頭">店頭</option>
              <option value="出張">出張</option>
              <option value="宅配">宅配買取</option>
            </select>
          </div>

          <div className="field">
            <label>買取場所{locationDisabled(form.purchase_method) ? '（担当店舗）' : ''}</label>
            {locationDisabled(form.purchase_method) ? (
              <input value="—" disabled title="店頭以外のため買取場所は表示しません（担当店舗は下で選択）" />
            ) : (
              <select
                value={storeId}
                onChange={(e) => setStoreId(e.target.value)}
                disabled={!!purchase}
              >
                {stores.map((s) => {
                  const label =
                    (s.article_config?.label as string | undefined) ||
                    s.name.replace(/^パワフルトレードセンター\s*/, '').replace(/店$/, '') ||
                    s.code
                  return (
                    <option key={s.id} value={s.id}>
                      {label}
                    </option>
                  )
                })}
              </select>
            )}
          </div>

          {locationDisabled(form.purchase_method) && (
            <div className="field">
              <label>担当店舗（記事の掲載店舗）</label>
              <select
                value={storeId}
                onChange={(e) => setStoreId(e.target.value)}
                disabled={!!purchase}
              >
                {stores.map((s) => {
                  const label =
                    (s.article_config?.label as string | undefined) ||
                    s.name.replace(/^パワフルトレードセンター\s*/, '').replace(/店$/, '') ||
                    s.code
                  return (
                    <option key={s.id} value={s.id}>
                      {label}
                    </option>
                  )
                })}
              </select>
            </div>
          )}

          {step === 'input' && (
            <div
              className={`dropzone${dragOver ? ' drag' : ''}`}
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                onPickFiles(e.dataTransfer.files, 'DETAIL')
              }}
            >
              <div>① 商品画像をドロップ、またはファイルを選択</div>
              <div className="meta" style={{ marginTop: 6 }}>
                メイン：全商品をまとめて写した記事用の写真／詳細：型番ラベルや箱などの接写（情報抽出用）
              </div>
              <div className="row" style={{ justifyContent: 'center', marginTop: 10 }}>
                <label className="btn btn-ghost">
                  メイン画像（記事用・まとめ）
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    hidden
                    onChange={(e) => onPickFiles(e.target.files, 'ARTICLE')}
                  />
                </label>
                <label className="btn btn-ghost">
                  詳細画像（ラベル・箱の接写）
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    hidden
                    onChange={(e) => onPickFiles(e.target.files, 'DETAIL')}
                  />
                </label>
              </div>
            </div>
          )}

          {previews.length > 0 && (
            <div className="thumbs">
              {previews.map((p) => (
                <div className="thumb" key={p.url}>
                  <img src={p.url} alt={p.file.name} />
                  <span className="tag">{imageTypeLabel(p.type)}</span>
                </div>
              ))}
            </div>
          )}

          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <label style={{ fontWeight: 600 }}>
              商品{products.length > 1 ? `（${products.length}種類）` : ''}
            </label>
            <button className="btn btn-ghost" type="button" onClick={addProduct}>
              ＋商品を追加
            </button>
          </div>
          <p className="meta" style={{ marginTop: 0 }}>
            種類ごとに1ブロックで入力してください。空欄は画像解析で補完されます。
          </p>

          {products.map((p, idx) => (
            <div
              key={idx}
              className="product-card"
              style={{
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                borderRadius: 8,
                padding: 10,
                marginBottom: 10,
              }}
            >
              <div
                className="row"
                style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}
              >
                <strong style={{ fontSize: '0.85rem' }}>商品 {idx + 1}</strong>
                {products.length > 1 && (
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() => removeProduct(idx)}
                    title="この商品を削除"
                  >
                    削除
                  </button>
                )}
              </div>
              <div className="field">
                <label>メーカー</label>
                <input
                  value={p.manufacturer}
                  onChange={(e) => updateProduct(idx, { manufacturer: e.target.value })}
                />
              </div>
              <div className="field">
                <label>商品</label>
                <input
                  value={p.product_name}
                  onChange={(e) => updateProduct(idx, { product_name: e.target.value })}
                />
              </div>
              <div className="field">
                <label>型式</label>
                <input
                  value={p.model_number}
                  onChange={(e) => updateProduct(idx, { model_number: e.target.value })}
                />
              </div>
              <div className="field">
                <label>状態</label>
                <input
                  value={p.condition}
                  onChange={(e) => updateProduct(idx, { condition: e.target.value })}
                />
              </div>
              <div className="row">
                <div className="field" style={{ flex: 1 }}>
                  <label>個数</label>
                  <input
                    type="number"
                    min={1}
                    value={p.quantity}
                    onChange={(e) => updateProduct(idx, { quantity: e.target.value })}
                  />
                </div>
                <div className="field" style={{ flex: 1 }}>
                  <label>単位</label>
                  <input
                    value={p.quantity_unit}
                    placeholder="点 / 台 / 本"
                    onChange={(e) => updateProduct(idx, { quantity_unit: e.target.value })}
                  />
                </div>
              </div>
            </div>
          ))}

          {(step === 'generate' || step === 'done') && (
            <div
              style={{
                marginTop: 12,
                paddingTop: 12,
                borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
              }}
            >
              <h3 style={{ fontSize: '0.92rem', margin: '0 0 4px' }}>記事作成用の追加情報（任意）</h3>
              <p className="meta" style={{ marginTop: 0 }}>
                商品が複数種類ある場合は、上の「＋商品を追加」で種類ごとに入力してください。
                カテゴリーや補足は記事全体に適用されます。
              </p>
              <div className="field">
                <label>カテゴリー</label>
                <input
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                />
              </div>
              <div className="field">
                <label>特徴・商品リスト（複数可）</label>
                <textarea
                  value={form.characteristics}
                  placeholder="例）&#10;・リョービ 振動ドリル PD-196VR ×1&#10;・マキタ インパクト TD172D ×2"
                  onChange={(e) => setForm({ ...form, characteristics: e.target.value })}
                />
              </div>
              <div className="field">
                <label>メモ（AIへのヒント）</label>
                <textarea
                  value={form.manual_notes}
                  onChange={(e) => setForm({ ...form, manual_notes: e.target.value })}
                />
              </div>
              <div className="field">
                <label>記事への追加指示</label>
                <textarea
                  value={form.user_instructions}
                  onChange={(e) => setForm({ ...form, user_instructions: e.target.value })}
                  placeholder="トーン、長さ、強調したいポイントなど…"
                />
              </div>
            </div>
          )}

          <div className="row">
            {step === 'input' && (
              <button
                className="btn btn-primary"
                type="button"
                disabled={busy}
                onClick={uploadAndAnalyze}
              >
                {busy ? '処理中…' : purchase ? '② 画像を再解析' : '② 画像を解析'}
              </button>
            )}
            {step === 'analyze' && (
              <button className="btn btn-warn" type="button" disabled>
                画像を解析中…
              </button>
            )}
            {(step === 'generate' || step === 'done') && (
              <>
                <button className="btn btn-ghost" type="button" disabled={busy} onClick={saveCorrections}>
                  修正を保存
                </button>
                <button className="btn btn-secondary" type="button" disabled={busy} onClick={runGenerate}>
                  {busy ? '生成中…' : '記事を生成'}
                </button>
              </>
            )}
            {purchase && (
              <button className="btn btn-ghost" type="button" disabled={busy} onClick={resetFlow}>
                新規テスト
              </button>
            )}
          </div>

          <div className="status-bar">
            {purchase && <span className={pillClass(purchase.status)}>買取: {purchase.status}</span>}
            {jobStatus && <span className={pillClass(jobStatus)}>ジョブ: {jobStatus}</span>}
            {article && <span className={pillClass(article.status)}>記事: {article.status}</span>}
          </div>
        </section>

        <aside>
          <section className="panel">
            <h2>結果</h2>
            <p className="lead">AI抽出結果、ジョブログ、生成記事のプレビュー。</p>

            {purchase?.ai_extraction && Object.keys(purchase.ai_extraction).length > 0 && (
              <>
                <h3 style={{ fontSize: '0.95rem', margin: '0 0 8px' }}>AI抽出結果</h3>
                <div className="result-box">{JSON.stringify(purchase.ai_extraction, null, 2)}</div>
              </>
            )}

            {version && !editing && (
              <div className="article-preview" style={{ marginTop: 16 }}>
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ margin: 0 }}>{version.title || '（タイトルなし）'}</h3>
                  <div className="row" style={{ gap: 6 }}>
                    <button className="btn btn-ghost" type="button" onClick={openTemplateEditor}>
                      テンプレート編集
                    </button>
                    <button className="btn btn-ghost" type="button" onClick={startEditing}>
                      編集・カスタマイズ
                    </button>
                  </div>
                </div>
                <div className="meta">
                  v{version.version_no}
                  {version.validation_outcome ? ` · 検証 ${version.validation_outcome}` : ''}
                  {article?.latest_similarity_score != null
                    ? ` · 類似率 ${(article.latest_similarity_score * 100).toFixed(1)}%`
                    : ''}
                </div>
                <div
                  className="body"
                  dangerouslySetInnerHTML={{
                    __html: toProxy(version.rendered_html || version.body || ''),
                  }}
                />
                {version.excerpt && (
                  <p style={{ marginTop: 12, color: 'var(--ink-soft)' }}>
                    <strong>抜粋:</strong> {version.excerpt}
                  </p>
                )}
                {(version.tag_suggestions?.length ?? 0) > 0 && (
                  <p className="meta">タグ: {version.tag_suggestions.join(', ')}</p>
                )}
              </div>
            )}

            {version && tplOpen && (
              <div className="article-preview" style={{ marginTop: 16 }}>
                <h3 style={{ margin: '0 0 4px' }}>店舗テンプレート編集（フッター・電話番号など）</h3>
                <p className="meta" style={{ marginTop: 0 }}>
                  ここでの変更はこの店舗の今後の記事すべてに反映されます（記事下部の定型文）。
                </p>
                <div className="field">
                  <label>感謝の一文（赤太字）</label>
                  <input
                    value={tpl.thanks_text}
                    onChange={(e) => setTpl({ ...tpl, thanks_text: e.target.value })}
                  />
                </div>
                <div className="row">
                  <div className="field" style={{ flex: 1 }}>
                    <label>総合ダイヤル</label>
                    <input
                      value={tpl.phone_general}
                      onChange={(e) => setTpl({ ...tpl, phone_general: e.target.value })}
                    />
                  </div>
                  <div className="field" style={{ flex: 1 }}>
                    <label>出張買取ダイヤル</label>
                    <input
                      value={tpl.phone_dispatch}
                      onChange={(e) => setTpl({ ...tpl, phone_dispatch: e.target.value })}
                    />
                  </div>
                </div>
                <div className="field">
                  <label>フッターHTML（住所・定型文）</label>
                  <textarea
                    style={{ minHeight: 220, fontFamily: 'monospace' }}
                    value={tpl.footer_html}
                    onChange={(e) => setTpl({ ...tpl, footer_html: e.target.value })}
                  />
                  <p className="meta">
                    電話番号を差し込む場合は <code>{'{phone_general}'}</code> /{' '}
                    <code>{'{phone_dispatch}'}</code> が使えます。
                  </p>
                </div>
                <div className="row">
                  <button className="btn btn-primary" type="button" disabled={busy} onClick={saveTemplate}>
                    {busy ? '保存中…' : 'テンプレートを保存'}
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={busy}
                    onClick={() => setTplOpen(false)}
                  >
                    閉じる
                  </button>
                </div>
              </div>
            )}

            {version && editing && (
              <div className="article-preview" style={{ marginTop: 16 }}>
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ margin: 0 }}>記事を編集</h3>
                  <label className="row" style={{ gap: 6, fontSize: '0.85rem' }}>
                    <input
                      type="checkbox"
                      checked={advanced}
                      onChange={(e) => setAdvanced(e.target.checked)}
                    />
                    詳細（全文HTML）
                  </label>
                </div>

                <div className="field">
                  <label>タイトル</label>
                  <input
                    value={edit.title}
                    onChange={(e) => setEdit({ ...edit, title: e.target.value })}
                  />
                </div>

                {!advanced ? (
                  <div className="field">
                    <label>本文（HTML — 固定見出し・フッターはそのまま）</label>
                    <textarea
                      style={{ minHeight: 200, fontFamily: 'monospace' }}
                      value={edit.body}
                      onChange={(e) => setEdit({ ...edit, body: e.target.value })}
                    />
                  </div>
                ) : (
                  <div className="field">
                    <label>組み立て済みHTML全文（詳細）</label>
                    <textarea
                      style={{ minHeight: 260, fontFamily: 'monospace' }}
                      value={edit.rendered_html}
                      onChange={(e) => setEdit({ ...edit, rendered_html: e.target.value })}
                    />
                  </div>
                )}

                <div className="field">
                  <label>抜粋</label>
                  <textarea
                    value={edit.excerpt}
                    onChange={(e) => setEdit({ ...edit, excerpt: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>タグ（カンマ区切り）</label>
                  <input
                    value={edit.tags}
                    onChange={(e) => setEdit({ ...edit, tags: e.target.value })}
                  />
                </div>

                <div className="row">
                  <button className="btn btn-primary" type="button" disabled={busy} onClick={saveEdit}>
                    {busy ? '保存中…' : '新バージョンとして保存'}
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={busy}
                    onClick={() => setEditing(false)}
                  >
                    キャンセル
                  </button>
                </div>

                <h4 style={{ margin: '16px 0 6px' }}>プレビュー</h4>
                <div
                  className="body"
                  dangerouslySetInnerHTML={{
                    __html: toProxy(advanced ? edit.rendered_html : edit.body),
                  }}
                />
              </div>
            )}

            {version && !editing && (
              <div style={{ marginTop: 16 }}>
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ margin: 0, fontSize: '0.95rem' }}>
                    年間買取10000件 パワトレ買取実績 (YARPP)
                  </h3>
                  <button className="btn btn-ghost" type="button" onClick={loadRelated}>
                    関連記事を取得
                  </button>
                </div>
                {relatedMsg && <p className="meta">{relatedMsg}</p>}
                {related && related.length > 0 && (
                  <div className="thumbs" style={{ marginTop: 10 }}>
                    {related.map((r) => (
                      <a
                        className="thumb"
                        key={r.id ?? r.link}
                        href={r.link}
                        target="_blank"
                        rel="noreferrer"
                        title={r.title}
                      >
                        {r.thumbnail ? (
                          <img src={r.thumbnail} alt={r.title} />
                        ) : (
                          <div style={{ padding: 8, fontSize: '0.75rem' }}>{r.title}</div>
                        )}
                        <span className="tag">{r.date?.slice(0, 10)}</span>
                      </a>
                    ))}
                  </div>
                )}
                {!related && !relatedMsg && (
                  <p className="meta">
                    WordPressへ公開後、YARPPが表示する関連記事4件を取得できます。
                  </p>
                )}
              </div>
            )}

            {!purchase && !version && (
              <div className="result-box" style={{ opacity: 0.7 }}>
                まだ結果はありません。画像をアップロードしてフローを実行してください。
              </div>
            )}
          </section>

          <section className="panel">
            <h2>アクティビティ</h2>
            <div className="result-box" style={{ maxHeight: 220 }}>
              {log.length ? log.join('\n') : '操作待ち…'}
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}
