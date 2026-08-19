import { useState } from 'react'
import type { Article, RelatedPost } from '../../api'
import { isPublished, plainText, toProxy } from '../../lib/format'
import { RefreshIcon } from '../../ui/Icons'
import { Banner, Field, PanelTitle, Section } from '../../ui/Layout'

/** Matches SIMILARITY_THRESHOLD on the backend; only warns, never blocks. */
const SIMILARITY_WARN_AT = 0.5

export type ArticleEditState = {
  title: string
  body: string
  excerpt: string
  category_suggestion: string
  tags: string
}

export type FooterEditState = {
  phone_general: string
  phone_dispatch: string
  line_url: string
}

function splitCategories(value: string): string[] {
  return value
    .split(/[,、]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

export default function ArticleStep({
  article,
  generating,
  jobStatus,
  log,
  wpCategories,
  edit,
  footer,
  related,
  busy,
  onEditChange,
  onFooterChange,
  onSave,
  onRegenerate,
  onBack,
  onSaveDraft,
  onPublish,
}: {
  article: Article | null
  generating: boolean
  jobStatus: string
  log: string[]
  wpCategories: Array<{ id: number; name: string }>
  edit: ArticleEditState
  footer: FooterEditState
  related: RelatedPost[]
  busy: boolean
  onEditChange: (patch: Partial<ArticleEditState>) => void
  onFooterChange: (patch: Partial<FooterEditState>) => void
  onSave: () => void
  onRegenerate: (instruction: string) => void
  onBack: () => void
  onSaveDraft: () => void
  onPublish: () => void
}) {
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')
  const [instruction, setInstruction] = useState('')
  const version = article?.current_version
  const similarity = article?.latest_similarity_score ?? null
  const similarityHigh = similarity !== null && similarity >= SIMILARITY_WARN_AT
  const published = isPublished(article?.status)
  const selectedCats = splitCategories(edit.category_suggestion)

  function toggleCategory(name: string) {
    const next = selectedCats.includes(name)
      ? selectedCats.filter((n) => n !== name)
      : [...selectedCats, name]
    onEditChange({ category_suggestion: next.join('、') })
  }

  if (generating || !article) {
    return (
      <div className="cf-panel">
        <PanelTitle title="記事を生成しています" sub="AI が本文を作成中です。" double />
        <div className="cf-progress">
          <div className="cf-progress__ring" />
          <div className="cf-progress__label">
            {jobStatus ? `ジョブ状態：${jobStatus}` : '準備中…'}
          </div>
          <div className="cf-progress__sub">
            画像の枚数によっては 1〜2 分ほどかかります。この画面のままお待ちください。
          </div>
        </div>
        {log.length > 0 && (
          <div className="cf-log">
            {log.map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <>
      <div className="cf-panel">
        <PanelTitle
          title="生成された記事"
          sub="内容を確認し、必要に応じて編集・再生成してください。"
          double
          action={
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                className={`cf-btn cf-btn--sm ${mode === 'preview' ? 'cf-btn--navy' : 'cf-btn--ghost'}`}
                onClick={() => setMode('preview')}
              >
                プレビュー
              </button>
              <button
                type="button"
                className={`cf-btn cf-btn--sm ${mode === 'edit' ? 'cf-btn--navy' : 'cf-btn--ghost'}`}
                onClick={() => setMode('edit')}
              >
                編集
              </button>
            </div>
          }
        />

        {similarityHigh && (
          <Banner kind="info">
            既存記事との類似率が {Math.round((similarity ?? 0) * 100)}%
            と高めです。このまま公開もできますが、本文の再生成をおすすめします。
          </Banner>
        )}

        <Section num={1} label="記事タイトル">
          <Field label="タイトル">
            <input
              className="cf-input"
              value={edit.title}
              onChange={(e) => onEditChange({ title: e.target.value })}
            />
          </Field>
          {similarity !== null && (
            <span className={`cf-badge cf-badge--${similarityHigh ? 'amber' : 'gray'}`}>
              類似率 {Math.round(similarity * 100)}%
            </span>
          )}
        </Section>

        <Section num={2} label={mode === 'preview' ? '本文プレビュー' : '本文の編集'}>
          {mode === 'preview' ? (
            <div
              className="cf-preview"
              dangerouslySetInnerHTML={{
                __html: toProxy(version?.rendered_html || '<p>本文がありません。</p>'),
              }}
            />
          ) : (
            <>
              <Field
                label="本文（AI が書いた可変部分のみ）"
                hint="固定の見出し・画像・フッターは保存時に自動で再構成されます。"
              >
                <textarea
                  className="cf-textarea"
                  style={{ minHeight: 260 }}
                  value={edit.body}
                  onChange={(e) => onEditChange({ body: e.target.value })}
                />
              </Field>
              <Field label="抜粋（メタディスクリプション）">
                <textarea
                  className="cf-textarea"
                  style={{ minHeight: 80 }}
                  value={edit.excerpt}
                  onChange={(e) => onEditChange({ excerpt: e.target.value })}
                />
              </Field>
              <Field
                label="カテゴリー"
                hint="複数選択できます。EXPERIENCE は公開時に自動で付きます。"
              >
                <div className="cf-checks">
                  {wpCategories.map((c) => (
                    <label key={c.id} className="cf-check">
                      <input
                        type="checkbox"
                        checked={selectedCats.includes(c.name)}
                        onChange={() => toggleCategory(c.name)}
                      />
                      {c.name}
                    </label>
                  ))}
                </div>
              </Field>
              <Field label="タグ" hint="カンマ区切り。場所（市区町村）は付けないでください。">
                <input
                  className="cf-input"
                  value={edit.tags}
                  onChange={(e) => onEditChange({ tags: e.target.value })}
                />
              </Field>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="cf-btn cf-btn--navy"
                  onClick={onSave}
                  disabled={busy}
                >
                  編集内容を保存
                </button>
              </div>
            </>
          )}
        </Section>

        <Section
          num={3}
          label="記事フッター（電話・LINE）"
          note="この店舗の全記事に使われる定型文です。電話番号を変えると次回以降の記事にも反映されます。"
        >
          <div className="cf-grid-2">
            <Field label="総合ダイヤル">
              <input
                className="cf-input"
                value={footer.phone_general}
                onChange={(e) => onFooterChange({ phone_general: e.target.value })}
              />
            </Field>
            <Field label="出張買取専用ダイヤル">
              <input
                className="cf-input"
                value={footer.phone_dispatch}
                onChange={(e) => onFooterChange({ phone_dispatch: e.target.value })}
              />
            </Field>
          </div>
          <Field label="LINE査定URL">
            <input
              className="cf-input"
              value={footer.line_url}
              onChange={(e) => onFooterChange({ line_url: e.target.value })}
            />
          </Field>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="button" className="cf-btn cf-btn--navy" onClick={onSave} disabled={busy}>
              フッターを保存して本文を更新
            </button>
          </div>
        </Section>

        <Section
          num={4}
          label="関連記事"
          note="公開サイトと同じく、関連する買取実績を最大4件自動で選びます。"
        >
          {related.length === 0 ? (
            <p className="cf-section__note" style={{ margin: 0 }}>
              まだ候補がありません。下書き保存または公開のあと、WordPress側の関連記事も表示されます。
            </p>
          ) : (
            <div className="cf-related">
              {related.slice(0, 4).map((post, i) => (
                <a
                  key={post.id ?? `${post.link}-${i}`}
                  className="cf-related__card"
                  href={post.link || undefined}
                  target={post.link ? '_blank' : undefined}
                  rel="noreferrer"
                >
                  {post.thumbnail && <img src={post.thumbnail} alt="" />}
                  <span className="cf-related__title">{plainText(post.title)}</span>
                </a>
              ))}
            </div>
          )}
        </Section>

        <Section num={5} label="再生成" note="指示を添えて本文を書き直せます（履歴は保持されます）。">
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <input
              className="cf-input"
              placeholder="例：もう少し短く、現場感を強めに"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
            />
            <button
              type="button"
              className="cf-btn cf-btn--outline"
              onClick={() => onRegenerate(instruction)}
              disabled={busy}
            >
              <RefreshIcon />
              再生成
            </button>
          </div>
        </Section>
      </div>

      <div className="cf-actionrow" style={{ marginTop: 22 }}>
        <button
          type="button"
          className="cf-btn cf-btn--ghost cf-btn--lg"
          onClick={onBack}
          disabled={busy}
        >
          抽出内容へ戻る
        </button>
        {!published && (
          <button
            type="button"
            className="cf-btn cf-btn--gold cf-btn--lg"
            onClick={onSaveDraft}
            disabled={busy}
          >
            下書きとして保存
          </button>
        )}
        <button
          type="button"
          className="cf-btn cf-btn--navy cf-btn--lg"
          onClick={onPublish}
          disabled={busy}
        >
          {published ? '公開内容を更新する' : 'この内容で公開する'}
        </button>
      </div>
    </>
  )
}
