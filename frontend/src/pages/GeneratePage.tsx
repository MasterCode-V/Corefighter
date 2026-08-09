import { useCallback, useEffect, useState } from 'react'
import {
  analyzeImages,
  createPurchase,
  deletePurchaseImage,
  editArticle,
  generateArticle,
  getArticle,
  getPurchase,
  listArticles,
  pollJob,
  regenerateArticle,
  submitForApproval,
  updatePurchase,
  uploadImage,
  type Article,
  type Persona,
  type Product,
  type Purchase,
  type PurchaseImage,
  type Store,
  type User,
} from '../api'
import { explainWorkflowError, todayIso } from '../lib/format'
import { Banner, Stepper } from '../ui/Layout'
import ArticleStep, { type ArticleEditState } from './generate/ArticleStep'
import BasicStep, { type BasicForm } from './generate/BasicStep'
import DoneStep from './generate/DoneStep'
import ReviewStep from './generate/ReviewStep'
import {
  areaIsManual,
  buildUserInstructions,
  emptyProduct,
  type ProductRow,
  type TopicId,
} from './generate/types'

const STEPS = ['基本情報・画像', '抽出内容確認', '記事生成', '完了']

function rowsFromPurchase(purchase: Purchase, previous: ProductRow[]): ProductRow[] {
  const detail = purchase.images.filter((i) => i.image_type === 'DETAIL')
  const source = purchase.products?.length
    ? purchase.products
    : [
        {
          manufacturer: purchase.manufacturer,
          product_name: purchase.product_name,
          model_number: purchase.model_number,
          condition: purchase.condition,
          quantity: purchase.quantity,
          quantity_unit: purchase.quantity_unit,
        } as Product,
      ]
  return source.map((p, index) => ({
    key: previous[index]?.key || emptyProduct().key,
    manufacturer: p.manufacturer || '',
    product_name: p.product_name || '',
    model_number: p.model_number || '',
    condition: p.condition || '',
    quantity: String(p.quantity ?? 1),
    quantity_unit: p.quantity_unit || '点',
    files: [],
    images: detail.filter((img) =>
      img.product_index === null || img.product_index === undefined
        ? index === 0
        : img.product_index === index,
    ),
  }))
}

export default function GeneratePage({
  token,
  user,
  stores,
  personas,
  wpCategories,
  articleId,
  onGoOps,
  onGoList,
  onOpenArticle,
}: {
  token: string
  user: User
  stores: Store[]
  personas: Persona[]
  wpCategories: Array<{ id: number; name: string }>
  articleId?: string
  onGoOps: () => void
  onGoList: () => void
  onOpenArticle: (articleId?: string) => void
}) {
  const isAdmin = user.role === 'ADMIN'

  const [step, setStep] = useState(0)
  const [storeId, setStoreId] = useState(user.store_id || '')
  const [personaId, setPersonaId] = useState('')
  const [form, setForm] = useState<BasicForm>({
    purchase_date: todayIso(),
    purchase_method: '店頭',
    purchase_area: '—',
  })
  const [products, setProducts] = useState<ProductRow[]>([emptyProduct()])
  const [mainFiles, setMainFiles] = useState<File[]>([])
  const [mainImages, setMainImages] = useState<PurchaseImage[]>([])

  const [purchase, setPurchase] = useState<Purchase | null>(null)
  const [article, setArticle] = useState<Article | null>(null)
  const [topicFlags, setTopicFlags] = useState<Record<string, boolean>>({})
  const [freeText, setFreeText] = useState('')
  const [edit, setEdit] = useState<ArticleEditState>({
    title: '',
    body: '',
    excerpt: '',
    category_suggestion: '',
    tags: '',
  })

  const [busy, setBusy] = useState(false)
  const [hydrating, setHydrating] = useState(Boolean(articleId))
  const [generating, setGenerating] = useState(false)
  const [jobStatus, setJobStatus] = useState('')
  const [log, setLog] = useState<string[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    if (!storeId && stores.length) setStoreId(user.store_id || stores[0].id)
  }, [stores, storeId, user.store_id])

  useEffect(() => {
    if (!personaId && personas.length) setPersonaId(personas[0].id)
  }, [personas, personaId])

  const pushLog = useCallback((message: string) => {
    setLog((prev) => [`${new Date().toLocaleTimeString()}  ${message}`, ...prev].slice(0, 40))
  }, [])

  const applyArticle = useCallback((next: Article) => {
    setArticle(next)
    const v = next.current_version
    setEdit({
      title: v?.title || '',
      body: v?.body || '',
      excerpt: v?.excerpt || '',
      category_suggestion: v?.category_suggestion || '',
      tags: (v?.tag_suggestions || []).join(', '),
    })
  }, [])

  /* ----------------------------------------------------- load for editing */

  useEffect(() => {
    if (!articleId) {
      setHydrating(false)
      return
    }
    let cancelled = false
    ;(async () => {
      setBusy(true)
      setHydrating(true)
      setError('')
      try {
        const loaded = await getArticle(token, articleId)
        if (cancelled) return
        applyArticle(loaded)
        setStoreId(loaded.store_id || '')
        const p = await getPurchase(token, loaded.purchase_id)
        if (cancelled) return
        setPurchase(p)
        setPersonaId(p.persona_id || '')
        setForm({
          purchase_date: p.purchase_date || todayIso(),
          purchase_method: p.purchase_method || '店頭',
          purchase_area: p.purchase_area || '—',
        })
        setProducts(rowsFromPurchase(p, []))
        setMainImages(p.images.filter((i) => i.image_type === 'ARTICLE'))
        setStep(2)
      } catch (err) {
        if (!cancelled) setError(explainWorkflowError(err, '記事の読み込みに失敗しました'))
      } finally {
        if (!cancelled) {
          setBusy(false)
          setHydrating(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [articleId, token, applyArticle])

  /* --------------------------------------------------------- product edit */

  function patchProduct(index: number, patch: Partial<ProductRow>) {
    setProducts((prev) => prev.map((p, i) => (i === index ? { ...p, ...patch } : p)))
  }

  function addProduct() {
    setProducts((prev) => [...prev, emptyProduct()])
  }

  function removeProduct(index: number) {
    setProducts((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)))
  }

  function addDetailFiles(index: number, files: File[]) {
    setProducts((prev) =>
      prev.map((p, i) => (i === index ? { ...p, files: [...p.files, ...files].slice(0, 8) } : p)),
    )
  }

  function removeDetailFile(index: number, fileIndex: number) {
    setProducts((prev) =>
      prev.map((p, i) =>
        i === index ? { ...p, files: p.files.filter((_, k) => k !== fileIndex) } : p,
      ),
    )
  }

  async function removeStoredImage(image: PurchaseImage) {
    if (!purchase) return
    setBusy(true)
    try {
      await deletePurchaseImage(token, purchase.id, image.id)
      const fresh = await getPurchase(token, purchase.id)
      setPurchase(fresh)
      setMainImages(fresh.images.filter((i) => i.image_type === 'ARTICLE'))
      setProducts((prev) => rowsFromPurchase(fresh, prev))
      pushLog('画像を削除しました')
    } catch (err) {
      setError(explainWorkflowError(err, '画像の削除に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  /* ------------------------------------------------------------ persisting */

  function productsPayload(): Product[] {
    return products.map((p, index) => ({
      sort_order: index,
      manufacturer: p.manufacturer.trim() || undefined,
      product_name: p.product_name.trim() || undefined,
      model_number: p.model_number.trim() || undefined,
      condition: p.condition.trim() || undefined,
      quantity: Number(p.quantity) > 0 ? Number(p.quantity) : 1,
      quantity_unit: p.quantity_unit.trim() || '点',
    }))
  }

  /** Create/update the purchase and upload every image the user picked. */
  const syncPurchase = useCallback(
    async (): Promise<Purchase> => {
      if (!storeId) throw new Error('保存できません。理由：掲載店舗が未選択です')
      // Product name/maker/model may be empty — AI fills them after analysis.
      const productRows = productsPayload()
      const hasProductData = productRows.some(
        (p) => p.manufacturer || p.product_name || p.model_number || p.condition,
      )
      const area =
        form.purchase_area.trim() || (areaIsManual(form.purchase_method) ? '' : '—')
      const payload = {
        persona_id: personaId || null,
        purchase_date: form.purchase_date || undefined,
        purchase_method: form.purchase_method || undefined,
        purchase_area: area || undefined,
        ...(hasProductData ? { products: productRows } : {}),
      }

      let current = purchase
      if (current) {
        current = await updatePurchase(token, current.id, {
          ...payload,
          ...(hasProductData ? { products: productRows } : {}),
        })
      } else {
        current = await createPurchase(token, { store_id: storeId, ...payload })
        pushLog(`買取データ ${current.id.slice(0, 8)}… を作成しました`)
        // Let the create response finish closing the socket before multipart upload.
        await new Promise((r) => setTimeout(r, 300))
      }

      let order = current.images.length
      for (const file of mainFiles) {
        await uploadImage(token, current.id, file, 'ARTICLE', order++)
        pushLog(`メイン画像をアップロード: ${file.name}`)
      }
      for (let index = 0; index < products.length; index++) {
        for (const file of products[index].files) {
          await uploadImage(token, current.id, file, 'DETAIL', order++, index)
          pushLog(`商品${index + 1}の詳細画像をアップロード: ${file.name}`)
        }
      }

      const fresh = await getPurchase(token, current.id)
      setPurchase(fresh)
      setMainFiles([])
      setMainImages(fresh.images.filter((i) => i.image_type === 'ARTICLE'))
      setProducts((prev) => rowsFromPurchase(fresh, prev))
      return fresh
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, storeId, personaId, form, products, mainFiles, purchase, pushLog],
  )

  async function saveDraft() {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await syncPurchase()
      setNotice('下書きを保存しました。あとから記事一覧の「編集」で再開できます。')
    } catch (err) {
      setError(explainWorkflowError(err, '下書き保存に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  /* --------------------------------------------------------------- analyze */

  async function runAnalyze() {
    setError('')
    setNotice('')
    if (!storeId) {
      setError('画像解析できません。理由：掲載店舗が未選択です。店舗を選んでから実行してください。')
      return
    }
    const hasImages =
      mainFiles.length + mainImages.length > 0 ||
      products.some((p) => p.files.length + p.images.length > 0)
    if (!hasImages) {
      setError(
        '画像解析できません。理由：解析する画像がありません。メイン画像を1枚追加してください（メーカー・商品名は空のままで大丈夫です）。',
      )
      return
    }
    setBusy(true)
    try {
      const fresh = await syncPurchase()
      pushLog('画像解析ジョブを開始しました')
      setJobStatus('QUEUED')
      const { job_id } = await analyzeImages(token, fresh.id)
      const job = await pollJob(token, job_id, (j) => {
        setJobStatus(j.status)
        pushLog(`解析ジョブ: ${j.status}`)
      })
      if (job.status !== 'COMPLETED') {
        throw new Error(
          job.error
            ? `画像解析に失敗しました。理由：${job.error}`
            : '画像解析に失敗しました。理由：ジョブが完了しませんでした。',
        )
      }
      const analysed = await getPurchase(token, fresh.id)
      setPurchase(analysed)
      setProducts((prev) => rowsFromPurchase(analysed, prev))
      setMainImages(analysed.images.filter((i) => i.image_type === 'ARTICLE'))
      pushLog('解析が完了しました')
      setStep(1)
    } catch (err) {
      setError(explainWorkflowError(err, '画像解析に失敗しました'))
    } finally {
      setBusy(false)
      setJobStatus('')
    }
  }

  /* -------------------------------------------------------------- generate */

  async function runGenerate() {
    if (!purchase) {
      setError(
        '記事を生成できません。理由：買取データがまだありません。先に画像解析（または下書き保存）を実行してください。',
      )
      return
    }
    // Empty AI fields are OK — fill a safe fallback so generation can proceed.
    const normalized = products.map((p, index) => ({
      ...p,
      product_name: p.product_name.trim() || `買取商品${products.length > 1 ? index + 1 : ''}`.trim(),
      quantity: p.quantity || '1',
      quantity_unit: p.quantity_unit.trim() || '点',
    }))
    if (normalized.some((p, i) => p.product_name !== products[i].product_name)) {
      setProducts(normalized)
    }
    setError('')
    setNotice('')
    setBusy(true)
    setGenerating(true)
    setStep(2)
    try {
      await updatePurchase(token, purchase.id, {
        persona_id: personaId || null,
        purchase_date: form.purchase_date || undefined,
        purchase_method: form.purchase_method || undefined,
        purchase_area: form.purchase_area || undefined,
        products: normalized.map((p, index) => ({
          sort_order: index,
          manufacturer: p.manufacturer.trim() || undefined,
          product_name: p.product_name.trim(),
          model_number: p.model_number.trim() || undefined,
          condition: p.condition.trim() || undefined,
          quantity: Number(p.quantity) > 0 ? Number(p.quantity) : 1,
          quantity_unit: p.quantity_unit.trim() || '点',
        })),
      })
      pushLog('記事生成ジョブを開始しました')
      setJobStatus('QUEUED')
      const { job_id } = await generateArticle(
        token,
        purchase.id,
        buildUserInstructions(topicFlags, freeText),
      )
      const job = await pollJob(token, job_id, (j) => {
        setJobStatus(j.status)
        pushLog(`生成ジョブ: ${j.status}`)
      })
      if (job.status !== 'COMPLETED') {
        throw new Error(
          job.error
            ? `記事生成に失敗しました。理由：${job.error}`
            : '記事生成に失敗しました。理由：ジョブが完了しませんでした。',
        )
      }

      pushLog('記事と類似率チェックの完了を待っています…')
      let found: Article | null = null
      for (let i = 0; i < 40; i++) {
        const list = await listArticles(token)
        const match = list.find((a) => a.purchase_id === purchase.id)
        if (match?.current_version?.title) {
          found = await getArticle(token, match.id)
          const stillChecking =
            found.status === 'DRAFT' && found.latest_similarity_score === null && i < 20
          if (!stillChecking) break
        }
        await new Promise((r) => setTimeout(r, 1500))
      }
      if (!found) {
        throw new Error(
          '記事生成に失敗しました。理由：生成ジョブは終わりましたが記事が見つかりませんでした。運用画面のジョブログを確認してください。',
        )
      }
      applyArticle(found)
      pushLog(`記事の準備が完了しました（${found.status}）`)
    } catch (err) {
      setError(explainWorkflowError(err, '記事生成に失敗しました'))
      setStep(1)
    } finally {
      setGenerating(false)
      setBusy(false)
      setJobStatus('')
    }
  }

  /* ------------------------------------------------------- article editing */

  async function saveEdit() {
    if (!article) return
    setBusy(true)
    setError('')
    try {
      const updated = await editArticle(token, article.id, {
        title: edit.title,
        body: edit.body,
        excerpt: edit.excerpt,
        category_suggestion: edit.category_suggestion || undefined,
        tag_suggestions: edit.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
      })
      applyArticle(await getArticle(token, updated.id))
      setNotice('記事を保存しました。')
      pushLog('記事を編集して新しいバージョンを作成しました')
    } catch (err) {
      setError(explainWorkflowError(err, '編集の保存に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  async function runRegenerate(instruction: string) {
    if (!article) return
    setBusy(true)
    setGenerating(true)
    setError('')
    try {
      const { job_id } = await regenerateArticle(token, article.id, instruction || undefined)
      const job = await pollJob(token, job_id, (j) => {
        setJobStatus(j.status)
        pushLog(`再生成ジョブ: ${j.status}`)
      })
      if (job.status !== 'COMPLETED') throw new Error(job.error || '再生成に失敗しました')
      applyArticle(await getArticle(token, article.id))
      setNotice('記事を再生成しました。')
    } catch (err) {
      setError(explainWorkflowError(err, '再生成に失敗しました'))
    } finally {
      setGenerating(false)
      setBusy(false)
      setJobStatus('')
    }
  }

  async function submitApproval() {
    if (!article) return
    setBusy(true)
    setError('')
    try {
      const updated = await submitForApproval(token, article.id)
      applyArticle(await getArticle(token, updated.id))
      setSubmitted(true)
    } catch (err) {
      setError(explainWorkflowError(err, '承認申請に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  function resetFlow() {
    setStep(0)
    setPurchase(null)
    setArticle(null)
    setProducts([emptyProduct()])
    setMainFiles([])
    setMainImages([])
    setTopicFlags({})
    setFreeText('')
    setSubmitted(false)
    setNotice('')
    setError('')
    setLog([])
    setForm({ purchase_date: todayIso(), purchase_method: '店頭', purchase_area: '—' })
    onOpenArticle(undefined)
  }

  return (
    <>
      <Stepper steps={STEPS} current={step} onJump={(i) => setStep(i)} />
      <div className="cf-page cf-page--narrow">
        {error && <Banner kind="error">{error}</Banner>}
        {notice && <Banner kind="ok">{notice}</Banner>}

        {hydrating && <div className="cf-empty">記事を読み込んでいます…</div>}

        {!hydrating && step === 0 && (
          <BasicStep
            stores={stores}
            personas={personas}
            storeId={storeId}
            personaId={personaId}
            form={form}
            products={products}
            mainFiles={mainFiles}
            mainImages={mainImages}
            busy={busy}
            canPickStore={isAdmin || !user.store_id}
            onStoreChange={setStoreId}
            onPersonaChange={setPersonaId}
            onFormChange={(patch) => setForm((f) => ({ ...f, ...patch }))}
            onProductChange={patchProduct}
            onAddProduct={addProduct}
            onRemoveProduct={removeProduct}
            onMainAdd={(files) => setMainFiles((prev) => [...prev, ...files].slice(0, 4))}
            onMainRemoveFile={(i) => setMainFiles((prev) => prev.filter((_, k) => k !== i))}
            onRemoveStoredImage={removeStoredImage}
            onDetailAdd={addDetailFiles}
            onDetailRemoveFile={removeDetailFile}
            onAnalyze={runAnalyze}
            onSaveDraft={saveDraft}
          />
        )}

        {!hydrating && step === 1 && (
          <ReviewStep
            products={products}
            mainImages={mainImages}
            topicFlags={topicFlags}
            freeText={freeText}
            busy={busy}
            onProductChange={patchProduct}
            onToggleTopic={(id: TopicId) =>
              setTopicFlags((prev) => ({ ...prev, [id]: !prev[id] }))
            }
            onFreeTextChange={setFreeText}
            onBack={() => setStep(0)}
            onGenerate={runGenerate}
          />
        )}

        {!hydrating && step === 2 && (
          <ArticleStep
            article={article}
            generating={generating}
            jobStatus={jobStatus}
            log={log}
            wpCategories={wpCategories}
            edit={edit}
            busy={busy}
            onEditChange={(patch) => setEdit((e) => ({ ...e, ...patch }))}
            onSave={saveEdit}
            onRegenerate={runRegenerate}
            onBack={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}

        {!hydrating && step === 3 && (
          <DoneStep
            article={article}
            stores={stores}
            busy={busy}
            submitted={submitted}
            onSubmitApproval={submitApproval}
            onGoOps={onGoOps}
            onGoList={onGoList}
            onNewArticle={resetFlow}
            onBackToArticle={() => setStep(2)}
          />
        )}
      </div>
    </>
  )
}
