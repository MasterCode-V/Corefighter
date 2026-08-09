import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  browseArticles,
  deleteArticle,
  getArticle,
  getArticleStats,
  type Article,
  type ArticleListItem,
  type StoreArticleStats,
  type Store,
} from '../api'
import {
  formatJaDate,
  plainText,
  shortStoreName,
  statusBadgeClass,
  statusLabel,
  STATUS_FILTER_OPTIONS,
  toProxy,
} from '../lib/format'
import { ExternalIcon, PlusIcon, SearchIcon, TrashIcon } from '../ui/Icons'
import { Banner, ConfirmDialog, Modal, Pager, PanelTitle } from '../ui/Layout'

const PAGE_SIZE = 30

const SORT_OPTIONS = [
  { value: 'updated_desc', label: '更新日が新しい順' },
  { value: 'updated_asc', label: '更新日が古い順' },
  { value: 'created_desc', label: '作成日が新しい順' },
  { value: 'created_asc', label: '作成日が古い順' },
]

type Filters = {
  keyword: string
  storeId: string
  status: string
  dateFrom: string
  dateTo: string
}

const EMPTY: Filters = { keyword: '', storeId: '', status: '', dateFrom: '', dateTo: '' }

export default function ArticleListPage({
  token,
  stores,
  isAdmin,
  onCreate,
  onEdit,
}: {
  token: string
  stores: Store[]
  isAdmin: boolean
  onCreate: () => void
  onEdit: (articleId: string) => void
}) {
  const [draft, setDraft] = useState<Filters>(EMPTY)
  const [applied, setApplied] = useState<Filters>(EMPTY)
  const [sort, setSort] = useState('updated_desc')
  const [page, setPage] = useState(1)

  const [items, setItems] = useState<ArticleListItem[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<StoreArticleStats[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [preview, setPreview] = useState<Article | null>(null)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<ArticleListItem | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [pageData, statData] = await Promise.all([
        browseArticles(token, {
          search: applied.keyword || undefined,
          storeId: applied.storeId || undefined,
          status: applied.status || undefined,
          dateFrom: applied.dateFrom || undefined,
          dateTo: applied.dateTo || undefined,
          order: sort,
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
        }),
        getArticleStats(token).catch(() => [] as StoreArticleStats[]),
      ])
      setItems(pageData.items)
      setTotal(pageData.total)
      setStats(statData)
    } catch (err) {
      setError(err instanceof Error ? err.message : '記事一覧の取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }, [token, applied, sort, page])

  useEffect(() => {
    void load()
  }, [load])

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const rangeFrom = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const rangeTo = Math.min(total, page * PAGE_SIZE)

  const storeOptions = useMemo(
    () => stores.map((s) => ({ value: s.id, label: s.name })),
    [stores],
  )

  function runSearch() {
    setPage(1)
    setApplied(draft)
  }

  function clearSearch() {
    setDraft(EMPTY)
    setApplied(EMPTY)
    setPage(1)
  }

  function toggleStoreChip(storeId: string) {
    const next = applied.storeId === storeId ? '' : storeId
    setDraft((d) => ({ ...d, storeId: next }))
    setApplied((a) => ({ ...a, storeId: next }))
    setPage(1)
  }

  async function openPreview(item: ArticleListItem) {
    setPreviewBusy(true)
    try {
      setPreview(await getArticle(token, item.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'プレビューの取得に失敗しました')
    } finally {
      setPreviewBusy(false)
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await deleteArticle(token, pendingDelete.id)
      setPendingDelete(null)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '削除に失敗しました')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <div className="cf-topaction">
        <button type="button" className="cf-btn cf-btn--navy" onClick={onCreate}>
          <PlusIcon />
          新規記事を作成
        </button>
      </div>

      <div className="cf-page">
        {stats.length > 0 && (
          <div className="cf-storechips">
            {stats.map((s) => (
              <button
                key={s.store_id}
                type="button"
                className={`cf-storechip${applied.storeId === s.store_id ? ' is-active' : ''}`}
                onClick={() => (isAdmin ? toggleStoreChip(s.store_id) : undefined)}
                disabled={!isAdmin}
                title={`${s.store_name} — 公開済み ${s.published}件 / 未公開 ${s.draft}件`}
              >
                <span className="cf-storechip__name">{shortStoreName(s.store_name)}</span>
                <span className="cf-storechip__counts">
                  <span className="cf-badge cf-badge--red">{s.published}</span>
                  <span className="cf-badge cf-badge--gray">{s.draft}</span>
                </span>
              </button>
            ))}
          </div>
        )}

        <div className="cf-panel">
          <PanelTitle title="記事検索" />
          <div className="cf-grid-3">
            <label className="cf-field">
              <span className="cf-field__label">キーワード</span>
              <span className="cf-input-search">
                <input
                  className="cf-input"
                  value={draft.keyword}
                  placeholder="記事タイトル・メーカー名・型式"
                  onChange={(e) => setDraft({ ...draft, keyword: e.target.value })}
                  onKeyDown={(e) => e.key === 'Enter' && runSearch()}
                />
                <SearchIcon />
              </span>
            </label>
            <label className="cf-field">
              <span className="cf-field__label">掲載店舗</span>
              <select
                className="cf-select"
                value={draft.storeId}
                disabled={!isAdmin}
                onChange={(e) => setDraft({ ...draft, storeId: e.target.value })}
              >
                <option value="">すべて</option>
                {storeOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="cf-field">
              <span className="cf-field__label">公開状態</span>
              <select
                className="cf-select"
                value={draft.status}
                onChange={(e) => setDraft({ ...draft, status: e.target.value })}
              >
                <option value="">すべて</option>
                {STATUS_FILTER_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {statusLabel(s)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="cf-grid-3" style={{ alignItems: 'end' }}>
            <div style={{ gridColumn: 'span 2' }}>
              <span className="cf-field__label">作成日</span>
              <div className="cf-daterange">
                <input
                  className="cf-input"
                  type="date"
                  value={draft.dateFrom}
                  onChange={(e) => setDraft({ ...draft, dateFrom: e.target.value })}
                />
                <span>〜</span>
                <input
                  className="cf-input"
                  type="date"
                  value={draft.dateTo}
                  onChange={(e) => setDraft({ ...draft, dateTo: e.target.value })}
                />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingBottom: 2 }}>
              <button type="button" className="cf-btn cf-btn--ghost" onClick={clearSearch}>
                検索条件をクリア
              </button>
              <button type="button" className="cf-btn cf-btn--navy" onClick={runSearch}>
                検索
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div style={{ marginTop: 16 }}>
            <Banner kind="error">{error}</Banner>
          </div>
        )}

        <div className="cf-resultbar">
          <span>
            {total}件中 {rangeFrom}-{rangeTo} 件を表示
          </span>
          <span className="cf-resultbar__sort">
            表示順
            <select
              className="cf-select"
              value={sort}
              onChange={(e) => {
                setSort(e.target.value)
                setPage(1)
              }}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </span>
        </div>

        {loading ? (
          <div className="cf-empty">読み込み中…</div>
        ) : items.length === 0 ? (
          <div className="cf-empty">
            条件に一致する記事がありません。右上の「新規記事を作成」から追加できます。
          </div>
        ) : (
          <div className="cf-cards">
            {items.map((item) => (
              <article className="cf-card" key={item.id}>
                <div className="cf-card__thumb">
                  {item.thumbnail_url ? (
                    <img
                      src={item.thumbnail_url}
                      alt={plainText(item.title) || 'メイン画像'}
                      loading="lazy"
                    />
                  ) : (
                    'メイン画像'
                  )}
                </div>
                <div className="cf-card__main">
                  <div className="cf-card__badges">
                    <span className={statusBadgeClass(item.status)}>
                      {statusLabel(item.status)}
                    </span>
                    <span className="cf-badge cf-badge--navyline" title={item.store_name}>
                      {shortStoreName(item.store_name)}
                    </span>
                  </div>
                  <div className="cf-card__line">
                    メーカー：{item.manufacturer || '—'}
                    {item.model_number ? `　${item.model_number}` : ''}
                  </div>
                  <div className="cf-card__line">商品数：{item.product_count}点</div>
                  {item.title && (
                    <div className="cf-card__title" title={plainText(item.title)}>
                      {plainText(item.title)}
                    </div>
                  )}
                  <div className="cf-card__rule" />
                  <div className="cf-card__meta">更新日：{formatJaDate(item.updated_at)}</div>
                  <div className="cf-card__actions">
                    <button
                      type="button"
                      className="cf-btn cf-btn--ghost"
                      onClick={() => openPreview(item)}
                      disabled={previewBusy}
                    >
                      プレビュー
                    </button>
                    <button
                      type="button"
                      className="cf-btn cf-btn--navy"
                      onClick={() => onEdit(item.id)}
                    >
                      編集
                    </button>
                    <button
                      type="button"
                      className="cf-iconbtn"
                      aria-label="この記事を削除"
                      title="この記事を削除"
                      onClick={() => setPendingDelete(item)}
                    >
                      <TrashIcon />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}

        <Pager page={page} pageCount={pageCount} onChange={setPage} />
      </div>

      {preview && (
        <Modal
          title={plainText(preview.current_version?.title) || '記事プレビュー'}
          onClose={() => setPreview(null)}
          wide
        >
          {preview.published_url && (
            <p style={{ marginTop: -6 }}>
              <a href={preview.published_url} target="_blank" rel="noreferrer">
                公開URLを開く <ExternalIcon />
              </a>
            </p>
          )}
          <div
            className="cf-preview"
            style={{ maxHeight: '62vh' }}
            dangerouslySetInnerHTML={{
              __html: toProxy(preview.current_version?.rendered_html || '<p>本文がありません。</p>'),
            }}
          />
          <div className="cf-modal__actions" style={{ marginTop: 16 }}>
            <button type="button" className="cf-btn cf-btn--ghost" onClick={() => setPreview(null)}>
              閉じる
            </button>
            <button
              type="button"
              className="cf-btn cf-btn--navy"
              onClick={() => {
                const id = preview.id
                setPreview(null)
                onEdit(id)
              }}
            >
              編集する
            </button>
          </div>
        </Modal>
      )}

      {pendingDelete && (
        <ConfirmDialog
          title="記事を削除しますか？"
          message={`「${plainText(pendingDelete.title) || pendingDelete.manufacturer || '無題の記事'}」と、紐づく買取データ・画像を削除します。WordPress に公開済みの投稿は削除されません。`}
          onConfirm={confirmDelete}
          onCancel={() => setPendingDelete(null)}
          busy={deleting}
        />
      )}
    </>
  )
}
