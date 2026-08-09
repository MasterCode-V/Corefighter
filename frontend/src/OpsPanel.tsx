import { useCallback, useEffect, useState } from 'react'
import {
  approvalDecision,
  createWordpressDraft,
  createWordpressSite,
  getArticle,
  getDashboardLogs,
  getDashboardSummary,
  getRecentJobs,
  getWaitingList,
  listArticlesByStatus,
  listPendingApprovals,
  listPurchases,
  listWordpressSites,
  pollJob,
  publishArticle,
  regenerateArticle,
  retryWordpress,
  searchArticles,
  submitForApproval,
  syncWordpressCorpus,
  triggerSimilarityCheck,
  updateWordpressSite,
} from './api'
import type { Article, DashboardSummary, Job, Purchase, Store } from './api'

type Props = {
  token: string
  stores: Store[]
  onOpenArticle?: (article: Article) => void
}

type Tab =
  | 'dashboard'
  | 'purchases'
  | 'articles'
  | 'waiting'
  | 'approval'
  | 'publish'
  | 'wp'

function statusJa(status: string) {
  const map: Record<string, string> = {
    DRAFT: '下書き',
    WAITING_LIST: '公開待機',
    SIMILARITY_WARNING: '類似率注意',
    NEEDS_CORRECTION: '要修正',
    WAITING_APPROVAL: '承認待ち',
    APPROVED: '承認済み',
    RETURNED: '差戻し',
    ON_HOLD: '保留',
    REJECTED: '却下',
    WORDPRESS_DRAFT: 'WP下書き',
    PUBLISHED: '公開済み',
    WORDPRESS_ERROR: 'WPエラー',
    PENDING: '処理中',
    ANALYZING: '解析中',
    ANALYZED: '解析済',
    GENERATING: '生成中',
    ARTICLE_READY: '記事準備完了',
  }
  return map[status] || status
}

export default function OpsPanel({ token, stores, onOpenArticle }: Props) {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [logs, setLogs] = useState<Array<{ id: string; level: string; message: string; created_at: string }>>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [waiting, setWaiting] = useState<Article[]>([])
  const [pending, setPending] = useState<Article[]>([])
  const [publishable, setPublishable] = useState<Article[]>([])
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [articles, setArticles] = useState<Article[]>([])
  const [articleSearch, setArticleSearch] = useState('')
  const [articleStatus, setArticleStatus] = useState('')
  const [wpSites, setWpSites] = useState<
    Array<{ id: string; store_id: string; name: string; base_url: string; username: string; is_active: boolean }>
  >([])
  const [note, setNote] = useState('')
  const [wpForm, setWpForm] = useState({
    store_id: '',
    base_url: 'https://www.buyersbox.co.jp',
    username: 'corefighter-api',
    app_password: '',
    name: '',
  })

  const refresh = useCallback(async () => {
    setError('')
    try {
      const [s, l, j, w, p, drafts, errors, approved, purch] = await Promise.all([
        getDashboardSummary(token),
        getDashboardLogs(token, 30),
        getRecentJobs(token, 15),
        getWaitingList(token),
        listPendingApprovals(token).catch(() => [] as Article[]),
        listArticlesByStatus(token, 'WORDPRESS_DRAFT'),
        listArticlesByStatus(token, 'WORDPRESS_ERROR'),
        listArticlesByStatus(token, 'APPROVED').catch(() => [] as Article[]),
        listPurchases(token, 40).catch(() => [] as Purchase[]),
      ])
      setSummary(s)
      setLogs(l)
      setJobs(j)
      setWaiting(w)
      setPending(p)
      setPublishable([...drafts, ...errors, ...approved])
      setPurchases(purch)

      const sites = (
        await Promise.all(stores.map((st) => listWordpressSites(token, st.id).catch(() => [])))
      ).flat()
      setWpSites(sites)
    } catch (err) {
      setError(err instanceof Error ? err.message : '運用データの取得に失敗しました')
    }
  }, [token, stores])

  useEffect(() => {
    if (!wpForm.store_id && stores[0]) {
      setWpForm((f) => ({ ...f, store_id: stores[0].id, name: `${stores[0].name} WP` }))
    }
  }, [stores, wpForm.store_id])

  const loadArticles = useCallback(async () => {
    try {
      const rows = await searchArticles(token, {
        status: articleStatus || undefined,
        search: articleSearch.trim() || undefined,
      })
      setArticles(rows)
    } catch (err) {
      setError(err instanceof Error ? err.message : '記事一覧の取得に失敗')
    }
  }, [token, articleStatus, articleSearch])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (tab === 'articles') void loadArticles()
  }, [tab, loadArticles])

  async function runJob(label: string, starter: () => Promise<{ job_id: string }>) {
    setBusy(true)
    setError('')
    setMsg(`${label}を開始…`)
    try {
      const { job_id } = await starter()
      const job = await pollJob(token, job_id, (j) => setMsg(`${label}: ${j.status}`))
      if (job.status === 'FAILED') throw new Error(job.error || `${label}に失敗しました`)
      setMsg(`${label}が完了しました`)
      await refresh()
      if (tab === 'articles') await loadArticles()
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label}に失敗しました`)
    } finally {
      setBusy(false)
    }
  }

  function titleOf(a: Article) {
    return a.current_version?.title || `記事 ${a.id.slice(0, 8)}…`
  }

  async function saveWordpress() {
    if (!wpForm.store_id || !wpForm.username || !wpForm.app_password) {
      setError('店舗・ユーザー名・アプリケーションパスワードは必須です')
      return
    }
    const pwLen = wpForm.app_password.replace(/\s/g, '').length
    if (pwLen < 16) {
      setMsg(
        `注意: アプリケーションパスワードが ${pwLen} 文字です。WordPress標準は約24文字です。不完全な可能性が高いですが、保存は続行します。`,
      )
    }
    setBusy(true)
    setError('')
    try {
      const existing = wpSites.find((s) => s.store_id === wpForm.store_id)
      const payload = {
        name: wpForm.name || 'WordPress',
        base_url: wpForm.base_url.replace(/\/$/, ''),
        username: wpForm.username,
        app_password: wpForm.app_password,
      }
      if (existing) {
        await updateWordpressSite(token, existing.id, payload)
        setMsg('WordPress接続を更新しました')
      } else {
        await createWordpressSite(token, wpForm.store_id, payload)
        setMsg('WordPress接続を登録しました')
      }
      setWpForm((f) => ({ ...f, app_password: '' }))
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'WordPress接続の保存に失敗')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>運用（フェーズ2）</h2>
        <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => void refresh()}>
          再読込
        </button>
      </div>
      <p className="lead">買取一覧・記事検索・公開待機・承認・WordPress下書き／公開・ダッシュボード</p>

      <div className="steps" style={{ marginBottom: 14, flexWrap: 'wrap' }}>
        {(
          [
            ['dashboard', 'ダッシュボード'],
            ['purchases', '買取一覧'],
            ['articles', '記事一覧'],
            ['waiting', '公開待機'],
            ['approval', '承認'],
            ['publish', 'WP公開'],
            ['wp', 'WP接続'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`step${tab === id ? ' active' : ''}`}
            onClick={() => setTab(id)}
            style={{ border: 'none', cursor: 'pointer' }}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {msg && <p className="meta">{msg}</p>}

      {(tab === 'waiting' || tab === 'approval') && (
        <div className="field">
          <label>メモ（承認／申請時）</label>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="任意" />
        </div>
      )}

      {tab === 'dashboard' && summary && (
        <>
          <div className="row" style={{ gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
            <span className="pill">待機 {summary.waiting_list}</span>
            <span className="pill warn">承認待ち {summary.waiting_approval}</span>
            <span className="pill ok">公開済 {summary.published}</span>
            <span className="pill err">失敗ジョブ {summary.failed_jobs}</span>
          </div>
          <h3 style={{ fontSize: '0.95rem' }}>最近のジョブ</h3>
          <div className="result-box" style={{ maxHeight: 180 }}>
            {jobs.length
              ? jobs.map((j) => `${j.job_type} · ${j.status}${j.error ? ` · ${j.error}` : ''}`).join('\n')
              : 'ジョブなし'}
          </div>
          <h3 style={{ fontSize: '0.95rem' }}>ログ／エラー履歴</h3>
          <div className="result-box" style={{ maxHeight: 180 }}>
            {logs.length
              ? logs.map((l) => `${l.created_at.slice(11, 19)} [${l.level}] ${l.message}`).join('\n')
              : 'ログなし'}
          </div>
          <button
            className="btn btn-secondary"
            type="button"
            disabled={busy}
            onClick={() => void runJob('コーパス同期', () => syncWordpressCorpus(token))}
          >
            WordPressコーパス同期
          </button>
        </>
      )}

      {tab === 'purchases' && (
        <div className="ops-list">
          {purchases.length === 0 && <p className="meta">買取データはありません。</p>}
          {purchases.map((p) => {
            const store = stores.find((s) => s.id === p.store_id)
            const name =
              p.products?.[0]?.product_name || p.product_name || p.manufacturer || '（名称なし）'
            return (
              <div key={p.id} className="ops-item">
                <div>
                  <strong>{name}</strong>
                  <div className="meta">
                    {statusJa(p.status)} · {store?.name || p.store_id.slice(0, 8)}
                    {p.purchase_date ? ` · ${p.purchase_date.slice(0, 10)}` : ''}
                    {p.purchase_method ? ` · ${p.purchase_method}` : ''}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {tab === 'articles' && (
        <>
          <div className="row" style={{ gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            <div className="field" style={{ flex: '1 1 180px', margin: 0 }}>
              <label>タイトル検索</label>
              <input
                value={articleSearch}
                onChange={(e) => setArticleSearch(e.target.value)}
                placeholder="キーワード"
              />
            </div>
            <div className="field" style={{ flex: '0 1 160px', margin: 0 }}>
              <label>ステータス</label>
              <select value={articleStatus} onChange={(e) => setArticleStatus(e.target.value)}>
                <option value="">すべて</option>
                <option value="WAITING_LIST">公開待機</option>
                <option value="WAITING_APPROVAL">承認待ち</option>
                <option value="WORDPRESS_DRAFT">WP下書き</option>
                <option value="PUBLISHED">公開済み</option>
                <option value="WORDPRESS_ERROR">WPエラー</option>
                <option value="RETURNED">差戻し</option>
              </select>
            </div>
            <button className="btn btn-primary" type="button" onClick={() => void loadArticles()}>
              検索
            </button>
          </div>
          <div className="ops-list">
            {articles.length === 0 && <p className="meta">該当する記事はありません。</p>}
            {articles.map((a) => (
              <div key={a.id} className="ops-item">
                <div>
                  <strong>{titleOf(a)}</strong>
                  <div className="meta">
                    {statusJa(a.status)}
                    {a.latest_similarity_score != null
                      ? ` · 類似率 ${(a.latest_similarity_score * 100).toFixed(1)}%`
                      : ''}
                  </div>
                </div>
                <div className="row">
                  <button className="btn btn-ghost" type="button" onClick={() => onOpenArticle?.(a)}>
                    プレビュー
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void runJob('類似率チェック', () => triggerSimilarityCheck(token, a.id))
                    }
                  >
                    類似率
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={busy}
                    onClick={() => void runJob('再生成', () => regenerateArticle(token, a.id))}
                  >
                    再生成
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'waiting' && (
        <div className="ops-list">
          {waiting.length === 0 && <p className="meta">公開待機リストは空です。</p>}
          {waiting.map((a) => (
            <div key={a.id} className="ops-item">
              <div>
                <strong>{titleOf(a)}</strong>
                <div className="meta">
                  {statusJa(a.status)}
                  {a.latest_similarity_score != null
                    ? ` · 類似率 ${(a.latest_similarity_score * 100).toFixed(1)}%`
                    : ''}
                </div>
              </div>
              <div className="row">
                <button className="btn btn-ghost" type="button" onClick={() => onOpenArticle?.(a)}>
                  開く
                </button>
                <button
                  className="btn btn-primary"
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    try {
                      await submitForApproval(token, a.id, note || undefined)
                      setMsg('承認申請しました')
                      setNote('')
                      await refresh()
                    } catch (err) {
                      setError(err instanceof Error ? err.message : '申請に失敗')
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  承認申請
                </button>
                <button
                  className="btn btn-ghost"
                  type="button"
                  disabled={busy}
                  onClick={() => void runJob('再生成', () => regenerateArticle(token, a.id))}
                >
                  再生成
                </button>
                <button
                  className="btn btn-ghost"
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    void runJob('類似率チェック', () => triggerSimilarityCheck(token, a.id))
                  }
                >
                  類似率
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'approval' && (
        <div className="ops-list">
          {pending.length === 0 && <p className="meta">承認待ちはありません（管理者のみ表示）。</p>}
          {pending.map((a) => (
            <div key={a.id} className="ops-item">
              <div>
                <strong>{titleOf(a)}</strong>
                <div className="meta">{statusJa(a.status)}</div>
              </div>
              <div className="row">
                <button className="btn btn-ghost" type="button" onClick={() => onOpenArticle?.(a)}>
                  開く
                </button>
                <button
                  className="btn btn-primary"
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    try {
                      await approvalDecision(token, a.id, 'approve', note || undefined)
                      setMsg('承認 → WP下書きジョブを投入しました')
                      setNote('')
                      await refresh()
                    } catch (err) {
                      setError(err instanceof Error ? err.message : '承認に失敗')
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  承認（WP下書き）
                </button>
                <button
                  className="btn btn-warn"
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    try {
                      await approvalDecision(token, a.id, 'return', note || undefined)
                      setMsg('差戻しました')
                      await refresh()
                    } catch (err) {
                      setError(err instanceof Error ? err.message : '差戻しに失敗')
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  差戻し
                </button>
                <button
                  className="btn btn-ghost"
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    try {
                      await approvalDecision(token, a.id, 'hold', note || undefined)
                      await refresh()
                    } catch (err) {
                      setError(err instanceof Error ? err.message : '保留に失敗')
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  保留
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'publish' && (
        <div className="ops-list">
          {publishable.length === 0 && <p className="meta">WP下書き／エラーの記事はありません。</p>}
          {publishable.map((a) => (
            <div key={a.id} className="ops-item">
              <div>
                <strong>{titleOf(a)}</strong>
                <div className="meta">
                  {statusJa(a.status)}
                  {a.wordpress_post_id ? ` · WP #${a.wordpress_post_id}` : ''}
                  {a.published_url ? ` · ${a.published_url}` : ''}
                </div>
              </div>
              <div className="row">
                {a.status === 'APPROVED' && (
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void runJob('WP下書き作成', () => createWordpressDraft(token, a.id))
                    }
                  >
                    WP下書き作成
                  </button>
                )}
                {a.status === 'WORDPRESS_DRAFT' && (
                  <button
                    className="btn btn-secondary"
                    type="button"
                    disabled={busy}
                    onClick={() => void runJob('公開', () => publishArticle(token, a.id))}
                  >
                    公開
                  </button>
                )}
                {a.status === 'WORDPRESS_ERROR' && (
                  <>
                    <button
                      className="btn btn-warn"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void runJob('下書き再試行', () =>
                          retryWordpress(token, a.id, 'WORDPRESS_DRAFT'),
                        )
                      }
                    >
                      下書き再試行
                    </button>
                    <button
                      className="btn btn-ghost"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void runJob('公開再試行', () =>
                          retryWordpress(token, a.id, 'WORDPRESS_PUBLISH'),
                        )
                      }
                    >
                      公開再試行
                    </button>
                  </>
                )}
                <button
                  className="btn btn-ghost"
                  type="button"
                  onClick={async () => {
                    const fresh = await getArticle(token, a.id)
                    onOpenArticle?.(fresh)
                  }}
                >
                  開く
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'wp' && (
        <>
          <p className="meta">
            管理画面: buyersbox.co.jp/wp/wp-admin · REST: https://www.buyersbox.co.jp/wp-json/
            <br />
            Application Password はユーザー編集画面で発行した<strong>完全な文字列</strong>
            （スペース付きでも可・通常24文字）を登録してください。
          </p>

          <div className="field">
            <label>店舗</label>
            <select
              value={wpForm.store_id}
              onChange={(e) => {
                const st = stores.find((x) => x.id === e.target.value)
                setWpForm((f) => ({
                  ...f,
                  store_id: e.target.value,
                  name: st ? `${st.name} WP` : f.name,
                }))
              }}
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>サイトURL</label>
            <input
              value={wpForm.base_url}
              onChange={(e) => setWpForm((f) => ({ ...f, base_url: e.target.value }))}
            />
          </div>
          <div className="field">
            <label>ユーザー名</label>
            <input
              value={wpForm.username}
              onChange={(e) => setWpForm((f) => ({ ...f, username: e.target.value }))}
            />
          </div>
          <div className="field">
            <label>アプリケーションパスワード</label>
            <input
              type="password"
              value={wpForm.app_password}
              onChange={(e) => setWpForm((f) => ({ ...f, app_password: e.target.value }))}
              placeholder="xxxx xxxx xxxx xxxx xxxx xxxx"
              autoComplete="off"
            />
          </div>
          <button className="btn btn-primary" type="button" disabled={busy} onClick={() => void saveWordpress()}>
            {wpSites.some((s) => s.store_id === wpForm.store_id) ? '接続を更新' : '接続を登録'}
          </button>

          <h3 style={{ fontSize: '0.95rem', marginTop: 18 }}>登録済み</h3>
          {wpSites.length === 0 && <p className="meta">まだ WordPress 接続が登録されていません。</p>}
          {wpSites.map((s) => {
            const store = stores.find((x) => x.id === s.store_id)
            return (
              <div key={s.id} className="ops-item">
                <div>
                  <strong>{store?.name || s.name}</strong>
                  <div className="meta">
                    {s.base_url} · {s.username} · {s.is_active ? '有効' : '無効'}
                  </div>
                </div>
              </div>
            )
          })}
        </>
      )}
    </section>
  )
}
