import type { PurchaseImage } from '../../api'
import { proxyImageUrl } from '../../lib/format'
import { CheckCircleIcon } from '../../ui/Icons'
import { Banner, Field, PanelTitle, Section } from '../../ui/Layout'
import {
  CONDITION_OPTIONS,
  TOPIC_OPTIONS,
  type ProductRow,
  type TopicId,
} from './types'

export default function ReviewStep({
  products,
  mainImages,
  topicFlags,
  freeText,
  busy,
  onProductChange,
  onToggleTopic,
  onFreeTextChange,
  onBack,
  onGenerate,
}: {
  products: ProductRow[]
  mainImages: PurchaseImage[]
  topicFlags: Record<string, boolean>
  freeText: string
  busy: boolean
  onProductChange: (index: number, patch: Partial<ProductRow>) => void
  onToggleTopic: (id: TopicId) => void
  onFreeTextChange: (value: string) => void
  onBack: () => void
  onGenerate: () => void
}) {
  const filled = products.filter((p) => p.manufacturer || p.product_name || p.model_number).length
  const missingNameIndexes = products
    .map((p, i) => (p.product_name.trim() ? null : i + 1))
    .filter((n): n is number => n !== null)

  return (
    <>
      <div className="cf-panel">
        <PanelTitle
          title="抽出内容の確認"
          sub="画像から読み取った内容です。誤りがあれば記事生成の前に修正してください。"
          double
          rule={false}
        />

        {missingNameIndexes.length > 0 && (
          <Banner kind="info">
            商品{missingNameIndexes.join('・')}
            の商品名が空です。このまま生成すると「買取商品」として進めます。分かっている場合は手入力してください。
          </Banner>
        )}

        <Section num={1} label="メイン画像">
          {mainImages.length ? (
            <div className="cf-thumbs" style={{ justifyContent: 'flex-start' }}>
              {mainImages.map((img) => (
                <div className="cf-thumb" key={img.id} style={{ width: 110, height: 84 }}>
                  <img src={proxyImageUrl(img.url)} alt="" />
                </div>
              ))}
            </div>
          ) : (
            <p className="cf-section__note" style={{ margin: 0 }}>
              メイン画像は登録されていません。アイキャッチには詳細画像の1枚目が使われます。
            </p>
          )}
        </Section>

        <Section num={2} label="商品情報" note="AI が抽出した内容を確認・修正できます。">
          {products.map((product, index) => (
            <div className="cf-product" key={product.key}>
              <div className="cf-product__head">
                <span className="cf-product__name">商品 {index + 1}</span>
                <span className="cf-badge cf-badge--green">
                  詳細画像 {product.images.length}枚
                </span>
              </div>
              <div className="cf-product__body">
                <div className="cf-product__left">
                  {product.images.length ? (
                    <div className="cf-thumbs">
                      {product.images.map((img) => (
                        <div className="cf-thumb" key={img.id}>
                          <img src={proxyImageUrl(img.url)} alt="" />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p>この商品に紐づく詳細画像はありません</p>
                  )}
                </div>
                <div className="cf-product__right">
                  <h4>抽出された商品情報</h4>
                  <div className="cf-inline-field">
                    <label htmlFor={`r-mk-${product.key}`}>メーカー</label>
                    <input
                      id={`r-mk-${product.key}`}
                      className="cf-input"
                      value={product.manufacturer}
                      onChange={(e) => onProductChange(index, { manufacturer: e.target.value })}
                    />
                  </div>
                  <div className="cf-inline-field">
                    <label htmlFor={`r-nm-${product.key}`}>商品名</label>
                    <input
                      id={`r-nm-${product.key}`}
                      className="cf-input"
                      value={product.product_name}
                      onChange={(e) => onProductChange(index, { product_name: e.target.value })}
                    />
                  </div>
                  <div className="cf-inline-field">
                    <label htmlFor={`r-mn-${product.key}`}>型式</label>
                    <input
                      id={`r-mn-${product.key}`}
                      className="cf-input"
                      value={product.model_number}
                      onChange={(e) => onProductChange(index, { model_number: e.target.value })}
                    />
                  </div>
                  <div className="cf-inline-field">
                    <label htmlFor={`r-cd-${product.key}`}>状態</label>
                    <select
                      id={`r-cd-${product.key}`}
                      className="cf-select"
                      value={product.condition}
                      onChange={(e) => onProductChange(index, { condition: e.target.value })}
                    >
                      <option value="">未選択</option>
                      {CONDITION_OPTIONS.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                      {product.condition &&
                        !CONDITION_OPTIONS.includes(
                          product.condition as (typeof CONDITION_OPTIONS)[number],
                        ) && <option value={product.condition}>{product.condition}</option>}
                    </select>
                  </div>
                  <div className="cf-grid-2">
                    <Field label="個数">
                      <input
                        className="cf-input"
                        type="number"
                        min={1}
                        value={product.quantity}
                        onChange={(e) => onProductChange(index, { quantity: e.target.value })}
                      />
                    </Field>
                    <Field label="単位">
                      <input
                        className="cf-input"
                        value={product.quantity_unit}
                        onChange={(e) => onProductChange(index, { quantity_unit: e.target.value })}
                      />
                    </Field>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </Section>

        <Section
          num={3}
          label="記事に入れる追加ネタ"
          note="チェックした話題を本文に自然に織り交ぜます（任意）。"
        >
          <div className="cf-checklist" style={{ maxHeight: 'none' }}>
            {TOPIC_OPTIONS.map((topic) => (
              <label className="cf-check" key={topic.id}>
                <input
                  type="checkbox"
                  checked={!!topicFlags[topic.id]}
                  onChange={() => onToggleTopic(topic.id)}
                />
                {topic.label}
              </label>
            ))}
          </div>
          <div style={{ marginTop: 14 }}>
            <Field
              label="スタッフ自由記入"
              hint="現場のひとこと、強調したい点など。電話番号・価格は本文に書かれません。"
            >
              <textarea
                className="cf-textarea"
                style={{ minHeight: 90 }}
                value={freeText}
                placeholder="例：まとめ買い歓迎、在庫処分品も対応可能など"
                onChange={(e) => onFreeTextChange(e.target.value)}
              />
            </Field>
          </div>
        </Section>
      </div>

      <div className="cf-summary">
        <CheckCircleIcon />
        商品 {products.length} 件
        <span className="cf-summary__dot">・</span>
        情報入力済み {filled} 件
      </div>

      <div className="cf-actionrow">
        <button
          type="button"
          className="cf-btn cf-btn--ghost cf-btn--lg"
          onClick={onBack}
          disabled={busy}
        >
          基本情報へ戻る
        </button>
        <button type="button" className="cf-cta" onClick={onGenerate} disabled={busy}>
          <span className="cf-cta__gold" />
          <span className="cf-cta__body">{busy ? '生成中…' : 'この内容で記事を生成'}</span>
          <span className="cf-cta__red" />
        </button>
      </div>
    </>
  )
}
