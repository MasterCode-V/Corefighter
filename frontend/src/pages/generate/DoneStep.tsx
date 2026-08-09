import type { Article, Store } from '../../api'
import { plainText, statusBadgeClass, statusLabel } from '../../lib/format'
import { CheckCircleIcon, ExternalIcon } from '../../ui/Icons'
import { Banner, PanelTitle, Section } from '../../ui/Layout'

export default function DoneStep({
  article,
  stores,
  busy,
  submitted,
  onSubmitApproval,
  onGoOps,
  onGoList,
  onNewArticle,
  onBackToArticle,
}: {
  article: Article | null
  stores: Store[]
  busy: boolean
  submitted: boolean
  onSubmitApproval: () => void
  onGoOps: () => void
  onGoList: () => void
  onNewArticle: () => void
  onBackToArticle: () => void
}) {
  const version = article?.current_version
  const store = stores.find((s) => s.id === article?.store_id)
  const canSubmit =
    !!article && ['DRAFT', 'WAITING_LIST', 'SIMILARITY_WARNING', 'RETURNED'].includes(article.status)

  return (
    <>
      <div className="cf-panel">
        <PanelTitle
          title="記事の作成が完了しました"
          sub="このあと「運用（承認・WP）」タブで承認と WordPress 公開を行います。"
          double
          rule={false}
        />

        {submitted && (
          <Banner kind="ok">
            承認申請を送信しました。運用タブの「承認待ち」から承認するとWordPressへ公開できます。
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
            <button
              type="button"
              className="cf-btn cf-btn--navy"
              onClick={onSubmitApproval}
              disabled={busy || !canSubmit}
              title={canSubmit ? undefined : '現在のステータスでは申請できません'}
            >
              承認へ提出する
            </button>
            <button type="button" className="cf-btn cf-btn--outline" onClick={onGoOps}>
              運用（承認・WP）タブへ
            </button>
            <button type="button" className="cf-btn cf-btn--ghost" onClick={onBackToArticle}>
              記事を編集し直す
            </button>
            <button type="button" className="cf-btn cf-btn--ghost" onClick={onGoList}>
              記事一覧へ戻る
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
