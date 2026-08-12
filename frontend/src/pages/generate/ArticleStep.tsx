import { useState } from 'react'
import type { Article } from '../../api'
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

export default function ArticleStep({
  article,
  generating,
  jobStatus,
  log,
  wpCategories,
  edit,
  busy,
  onEditChange,
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
  busy: boolean
  onEditChange: (patch: Partial<ArticleEditState>) => void
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

  if (generating || !article) {
    return (
      <div className="cf-panel">
        <PanelTitle title="記事を生成しています" sub="AI が本文を作成中です。" double rule={false} />
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
          rule={false}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <strong style={{ fontSize: 15 }}>
              {plainText(version?.title) || '（タイトル未生成）'}
            </strong>
            {similarity !== null && (
              <span className={`cf-badge cf-badge--${similarityHigh ? 'amber' : 'gray'}`}>
                類似率 {Math.round(similarity * 100)}%
              </span>
            )}
            <span className="cf-badge cf-badge--gray">v{version?.version_no ?? 1}</span>
          </div>
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
              <Field label="タイトル">
                <input
                  className="cf-input"
                  value={edit.title}
                  onChange={(e) => onEditChange({ title: e.target.value })}
                />
              </Field>
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
              <div className="cf-grid-2">
                <Field label="抜粋（メタディスクリプション）">
                  <textarea
                    className="cf-textarea"
                    style={{ minHeight: 80 }}
                    value={edit.excerpt}
                    onChange={(e) => onEditChange({ excerpt: e.target.value })}
                  />
                </Field>
                <div>
                  <Field label="カテゴリー">
                    <select
                      className="cf-select"
                      value={edit.category_suggestion}
                      onChange={(e) => onEditChange({ category_suggestion: e.target.value })}
                    >
                      <option value="">未指定</option>
                      {wpCategories.map((c) => (
                        <option key={c.id} value={c.name}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="タグ" hint="カンマ区切り">
                    <input
                      className="cf-input"
                      value={edit.tags}
                      onChange={(e) => onEditChange({ tags: e.target.value })}
                    />
                  </Field>
                </div>
              </div>
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

        <Section num={3} label="再生成" note="指示を添えて本文を書き直せます（履歴は保持されます）。">
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
