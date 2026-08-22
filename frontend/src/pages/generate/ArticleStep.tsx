import { useEffect, useMemo, useState } from 'react'
import type { Article, RelatedPost, WordpressTag } from '../../api'
import { isPublished, plainText, toProxy } from '../../lib/format'
import { RefreshIcon, SearchIcon, TrashIcon } from '../../ui/Icons'
import { Banner, Field, PanelTitle, Section } from '../../ui/Layout'
import RichTextEditor from '../../ui/RichTextEditor'

/** Matches SIMILARITY_THRESHOLD on the backend; only warns, never blocks. */
const SIMILARITY_WARN_AT = 0.5
const MAX_RELATED = 4

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
  footer_html: string
}

function splitList(value: string): string[] {
  return value
    .split(/[,、]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function relatedKey(post: RelatedPost): string {
  return post.article_id || (post.id != null ? `wp-${post.id}` : `${post.link}-${post.title}`)
}

export default function ArticleStep({
  article,
  generating,
  jobStatus,
  log,
  wpCategories,
  wpTags,
  edit,
  footer,
  related,
  relatedManual,
  relatedCandidates,
  relatedSearch,
  relatedSearching,
  busy,
  onEditChange,
  onFooterChange,
  onRelatedChange,
  onRelatedSearchChange,
  onRelatedSearch,
  onSaveRelated,
  onClearRelatedManual,
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
  wpTags: WordpressTag[]
  edit: ArticleEditState
  footer: FooterEditState
  related: RelatedPost[]
  relatedManual: boolean
  relatedCandidates: RelatedPost[]
  relatedSearch: string
  relatedSearching: boolean
  busy: boolean
  onEditChange: (patch: Partial<ArticleEditState>) => void
  onFooterChange: (patch: Partial<FooterEditState>) => void
  onRelatedChange: (items: RelatedPost[]) => void
  onRelatedSearchChange: (q: string) => void
  onRelatedSearch: () => void
  onSaveRelated: () => void
  onClearRelatedManual: () => void
  onSave: () => void
  onRegenerate: (instruction: string) => void
  onBack: () => void
  onSaveDraft: () => void
  onPublish: () => void
}) {
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')
  const [instruction, setInstruction] = useState('')
  const [tagFilter, setTagFilter] = useState('')
  const version = article?.current_version
  const similarity = article?.latest_similarity_score ?? null
  const similarityHigh = similarity !== null && similarity >= SIMILARITY_WARN_AT
  const published = isPublished(article?.status)
  const selectedCats = splitList(edit.category_suggestion)
  const selectedTags = splitList(edit.tags)

  const filteredWpTags = useMemo(() => {
    const needle = tagFilter.trim().toLowerCase()
    const rows = wpTags.filter((t) => t.name.trim())
    if (!needle) return rows.slice(0, 60)
    return rows.filter((t) => t.name.toLowerCase().includes(needle)).slice(0, 60)
  }, [wpTags, tagFilter])

  useEffect(() => {
    if (!relatedManual && related.length === 0) return
  }, [relatedManual, related.length])

  function toggleCategory(name: string) {
    const next = selectedCats.includes(name)
      ? selectedCats.filter((n) => n !== name)
      : [...selectedCats, name]
    onEditChange({ category_suggestion: next.join('、') })
  }

  function setTags(next: string[]) {
    onEditChange({ tags: next.join('、') })
  }

  function toggleTag(name: string) {
    if (selectedTags.includes(name)) setTags(selectedTags.filter((t) => t !== name))
    else setTags([...selectedTags, name])
  }

  function addRelated(post: RelatedPost) {
    if (related.length >= MAX_RELATED) return
    if (related.some((r) => relatedKey(r) === relatedKey(post))) return
    onRelatedChange([...related, post].slice(0, MAX_RELATED))
  }

  function removeRelated(post: RelatedPost) {
    onRelatedChange(related.filter((r) => relatedKey(r) !== relatedKey(post)))
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
              <Field
                label="タグ"
                hint="既存タグから選択できます。手入力も可能です（カンマ区切り）。場所（市区町村）は付けないでください。"
              >
                {selectedTags.length > 0 && (
                  <div className="cf-tagrow" style={{ marginBottom: 10 }}>
                    {selectedTags.map((t) => (
                      <button
                        key={t}
                        type="button"
                        className="cf-tagchip is-selected"
                        onClick={() => toggleTag(t)}
                        title="クリックで外す"
                      >
                        {t} ×
                      </button>
                    ))}
                  </div>
                )}
                <div className="cf-input-search" style={{ marginBottom: 8 }}>
                  <input
                    className="cf-input"
                    value={tagFilter}
                    placeholder="既存タグを検索"
                    onChange={(e) => setTagFilter(e.target.value)}
                  />
                  <SearchIcon />
                </div>
                {filteredWpTags.length > 0 ? (
                  <div className="cf-tagrow" style={{ marginBottom: 10 }}>
                    {filteredWpTags.map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        className={`cf-tagchip${selectedTags.includes(t.name) ? ' is-selected' : ''}`}
                        onClick={() => toggleTag(t.name)}
                      >
                        {t.name}
                        {t.count > 0 ? ` (${t.count})` : ''}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="cf-section__note" style={{ margin: '0 0 8px' }}>
                    既存タグを取得できませんでした。下の欄に手入力してください。
                  </p>
                )}
                <input
                  className="cf-input"
                  value={edit.tags}
                  placeholder="例：東苗穂店、VVF、電線"
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
          label="記事フッター（電話・LINE・キャンペーン文）"
          note="この店舗の全記事に使われる定型文です。太字・リンク・サイズ変更ができます。{phone_general} 等のプレースホルダは保存時に電話番号へ置換されます。"
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
          <Field label="フッターHTML（キャンペーン文・追加リンクなど）">
            <RichTextEditor
              value={footer.footer_html}
              onChange={(html) => onFooterChange({ footer_html: html })}
              disabled={busy}
              placeholder="例：期間限定キャンペーンのお知らせ…"
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
          note="最大4件。自動候補を使うか、WordPress公開済み記事から手動で選べます。手動選択は公開HTMLにも反映されます。"
        >
          <div className="cf-related-toolbar">
            <span className={`cf-badge ${relatedManual ? 'cf-badge--navyline' : 'cf-badge--gray'}`}>
              {relatedManual ? '手動選択' : '自動候補'}
            </span>
            <span className="cf-section__note" style={{ margin: 0 }}>
              {related.length}/{MAX_RELATED} 件
            </span>
            {relatedManual && (
              <button
                type="button"
                className="cf-btn cf-btn--ghost cf-btn--sm"
                onClick={onClearRelatedManual}
                disabled={busy}
              >
                自動に戻す
              </button>
            )}
          </div>

          {related.length === 0 ? (
            <p className="cf-section__note" style={{ margin: '0 0 12px' }}>
              まだ選ばれていません。下の検索から追加するか、公開後に自動候補を利用できます。
            </p>
          ) : (
            <div className="cf-related" style={{ marginBottom: 14 }}>
              {related.slice(0, MAX_RELATED).map((post, i) => (
                <div key={relatedKey(post) || i} className="cf-related__card cf-related__card--edit">
                  {post.thumbnail && <img src={post.thumbnail} alt="" />}
                  <span className="cf-related__title">{plainText(post.title)}</span>
                  <button
                    type="button"
                    className="cf-iconbtn"
                    aria-label="関連記事から外す"
                    onClick={() => removeRelated(post)}
                    disabled={busy}
                  >
                    <TrashIcon />
                  </button>
                </div>
              ))}
            </div>
          )}

          <Field
            label="WordPress公開済み記事から追加"
            hint="buyersboxの買取実績（EXPERIENCE）からキーワード検索。未入力で検索すると直近の公開記事を表示します。"
          >
            <div style={{ display: 'flex', gap: 8 }}>
              <span className="cf-input-search" style={{ flex: 1 }}>
                <input
                  className="cf-input"
                  value={relatedSearch}
                  placeholder="例：Makita、電線、VCTF"
                  onChange={(e) => onRelatedSearchChange(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && onRelatedSearch()}
                />
                <SearchIcon />
              </span>
              <button
                type="button"
                className="cf-btn cf-btn--outline"
                onClick={onRelatedSearch}
                disabled={busy || relatedSearching}
              >
                {relatedSearching ? '検索中…' : '検索'}
              </button>
            </div>
          </Field>

          {!relatedSearching && relatedCandidates.length === 0 && (
            <p className="cf-section__note" style={{ margin: '8px 0 0' }}>
              {relatedSearch.trim()
                ? '該当するWordPress公開記事が見つかりませんでした。別のキーワードをお試しください。'
                : '検索ボタンを押すと、WordPressの直近公開記事が候補として表示されます。'}
            </p>
          )}

          {relatedCandidates.length > 0 && (
            <div className="cf-related-candidates">
              {relatedCandidates.map((c) => {
                const already = related.some((r) => relatedKey(r) === relatedKey(c))
                const full = related.length >= MAX_RELATED
                return (
                  <button
                    key={relatedKey(c)}
                    type="button"
                    className="cf-related-candidate"
                    disabled={busy || already || full}
                    onClick={() => addRelated(c)}
                  >
                    <span>{plainText(c.title)}</span>
                    <span className="cf-related-candidate__action">
                      {already ? '選択済' : full ? '上限' : '追加'}
                    </span>
                  </button>
                )
              })}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
            <button
              type="button"
              className="cf-btn cf-btn--navy"
              onClick={onSaveRelated}
              disabled={busy}
            >
              関連記事を保存
            </button>
          </div>
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
