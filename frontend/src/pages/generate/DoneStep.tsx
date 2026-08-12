import type { Article, Store } from '../../api'
import { isPublished, plainText, statusBadgeClass, statusLabel } from '../../lib/format'
import { CheckCircleIcon, ExternalIcon } from '../../ui/Icons'
import { Banner, PanelTitle, Section } from '../../ui/Layout'

export default function DoneStep({
  article,
  stores,
  busy,
  outcome,
  onPublish,
  onSaveDraft,
  onGoOps,
  onGoList,
  onNewArticle,
  onBackToArticle,
}: {
  article: Article | null
  stores: Store[]
  busy: boolean
  outcome: 'draft' | 'published' | null
  onPublish: () => void
  onSaveDraft: () => void
  onGoOps: () => void
  onGoList: () => void
  onNewArticle: () => void
  onBackToArticle: () => void
}) {
  const version = article?.current_version
  const store = stores.find((s) => s.id === article?.store_id)
  const published = isPublished(article?.status)

  return (
    <>
      <div className="cf-panel">
        <PanelTitle
          title={published ? '記事を公開しました' : '記事を下書き保存しました'}
          sub={
            published
              ? 'WordPress に公開済みです。掲載ページからも確認できます。'
              : 'WordPress に下書きとして保存しました。内容を確認したら公開してください。'
          }
          double
          rule={false}
        />

        {outcome === 'published' && (
          <Banner kind="ok">公開が完了しました。反映まで数分かかる場合があります。</Banner>
        )}
        {outcome === 'draft' && (
          <Banner kind="ok">
            下書きを保存しました。記事一覧の「編集」からいつでも再開・公開できます。
          </Banner>
        )}

        <Section num={1} label="記事の概要">
          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <CheckCircleIcon size={18} />
              <strong style={{ fontSize: 15 }}>
                {plainText(version?.title) || '（タイトルなし）'}
              </strong>
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              {article && (
                <span className={statusBadgeClass(article.status)}>
                  {statusLabel(article.status)}
                </span>
              )}
              {store && <span className="cf-badge cf-badge--navyline">{store.name}</span>}
              {article?.latest_similarity_score !== null &&
                article?.latest_similarity_score !== undefined && (
                  <span className="cf-badge cf-badge--gray">
                    類似率 {Math.round(article.latest_similarity_score * 100)}%
                  </span>
                )}
            </div>
            {article?.published_url && (
              <a href={article.published_url} target="_blank" rel="noreferrer">
                公開ページを開く <ExternalIcon />
              </a>
            )}
            {version?.excerpt && (
              <p style={{ margin: 0, color: 'var(--muted)', fontSize: 12.5 }}>{version.excerpt}</p>
            )}
          </div>
        </Section>

        <Section num={2} label="次のアクション">
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {!published && (
              <>
                <button
                  type="button"
                  className="cf-btn cf-btn--navy"
                  onClick={onPublish}
                  disabled={busy}
                >
                  この記事を公開する
                </button>
                <button
                  type="button"
                  className="cf-btn cf-btn--gold"
                  onClick={onSaveDraft}
                  disabled={busy}
                >
                  下書きを更新する
                </button>
              </>
            )}
            <button type="button" className="cf-btn cf-btn--ghost" onClick={onBackToArticle}>
              記事を編集し直す
            </button>
            <button type="button" className="cf-btn cf-btn--outline" onClick={onGoList}>
              記事一覧へ
            </button>
            <button type="button" className="cf-btn cf-btn--ghost" onClick={onGoOps}>
              運用画面へ
            </button>
            <button type="button" className="cf-btn cf-btn--ghost" onClick={onNewArticle}>
              続けて新規作成
            </button>
          </div>
        </Section>
      </div>
    </>
  )
}
