import type { Persona, PurchaseImage, Store } from '../../api'
import { useEffect, useRef, useState } from 'react'
import { DotsIcon, LinkIcon, PlusIcon } from '../../ui/Icons'
import { Field, PanelTitle, Section } from '../../ui/Layout'
import { DetailImagePicker, MainImagePicker } from './ImagePicker'
import { CONDITION_OPTIONS, PURCHASE_METHODS, areaIsManual, type ProductRow } from './types'

export type BasicForm = {
  purchase_date: string
  purchase_method: string
  purchase_area: string
}

export default function BasicStep({
  stores,
  personas,
  storeId,
  personaId,
  form,
  products,
  mainFiles,
  mainImages,
  busy,
  canPickStore,
  onStoreChange,
  onPersonaChange,
  onFormChange,
  onProductChange,
  onAddProduct,
  onRemoveProduct,
  onClearProduct,
  onMainAdd,
  onMainRemoveFile,
  onRemoveStoredImage,
  onDetailAdd,
  onDetailRemoveFile,
  onAnalyze,
  onSaveDraft,
}: {
  stores: Store[]
  personas: Persona[]
  storeId: string
  personaId: string
  form: BasicForm
  products: ProductRow[]
  mainFiles: File[]
  mainImages: PurchaseImage[]
  busy: boolean
  canPickStore: boolean
  onStoreChange: (id: string) => void
  onPersonaChange: (id: string) => void
  onFormChange: (patch: Partial<BasicForm>) => void
  onProductChange: (index: number, patch: Partial<ProductRow>) => void
  onAddProduct: () => void
  onRemoveProduct: (index: number) => void
  onClearProduct: (index: number) => void
  onMainAdd: (files: File[]) => void
  onMainRemoveFile: (index: number) => void
  onRemoveStoredImage: (image: PurchaseImage) => void
  onDetailAdd: (index: number, files: File[]) => void
  onDetailRemoveFile: (index: number, fileIndex: number) => void
  onAnalyze: () => void
  onSaveDraft: () => void
}) {
  const manualArea = areaIsManual(form.purchase_method)
  const [openMenu, setOpenMenu] = useState<number | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (openMenu === null) return
    function onDoc(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpenMenu(null)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [openMenu])

  return (
    <>
      <div className="cf-panel">
        <PanelTitle title="記事生成の準備" double rule />

        <Section num={1} label="基本情報">
          <div className="cf-grid-2">
            <Field label="AI人格">
              <select
                className="cf-select"
                value={personaId}
                onChange={(e) => onPersonaChange(e.target.value)}
              >
                <option value="">未指定</option>
                {personas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="日付">
              <input
                className="cf-input"
                type="date"
                value={form.purchase_date}
                onChange={(e) => onFormChange({ purchase_date: e.target.value })}
              />
            </Field>
            <Field label="買取方法">
              <select
                className="cf-select"
                value={form.purchase_method}
                onChange={(e) =>
                  onFormChange({
                    purchase_method: e.target.value,
                    purchase_area: areaIsManual(e.target.value) ? '' : '—',
                  })
                }
              >
                {PURCHASE_METHODS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </Field>
            {/* 買取地区 is only relevant for 出張 / 宅配; hidden entirely for 店頭. */}
            {manualArea && (
              <Field label="買取地区" hint="例：札幌市白石区">
                <input
                  className="cf-input"
                  value={form.purchase_area}
                  placeholder="買取地区を入力"
                  onChange={(e) => onFormChange({ purchase_area: e.target.value })}
                />
              </Field>
            )}
            <Field label="掲載店舗" required>
              <select
                className="cf-select"
                value={storeId}
                disabled={!canPickStore}
                onChange={(e) => onStoreChange(e.target.value)}
              >
                <option value="">選択してください</option>
                {stores.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </Section>

        <Section num={2} label="メイン画像（記事用）">
          <MainImagePicker
            files={mainFiles}
            images={mainImages}
            disabled={busy}
            onAdd={onMainAdd}
            onRemoveFile={onMainRemoveFile}
            onRemoveStored={onRemoveStoredImage}
          />
        </Section>

        <Section
          num={3}
          label="商品別の詳細画像・情報"
          note="商品ごとにブロックを作成し、対応するラベル画像を登録してください。"
          action={
            <button
              type="button"
              className="cf-btn cf-btn--outline cf-btn--sm"
              onClick={onAddProduct}
              disabled={busy}
            >
              <PlusIcon />
              商品を追加
            </button>
          }
        >
          {products.map((product, index) => {
            const linked = product.files.length + product.images.length
            return (
              <div className="cf-product" key={product.key}>
                <div className="cf-product__head">
                  <span className="cf-product__name">商品 {index + 1}</span>
                  <span className={`cf-badge ${linked ? 'cf-badge--green' : 'cf-badge--gray'}`}>
                    詳細画像 {linked ? `${linked}枚` : '任意'}
                  </span>
                  <span className="cf-section__spacer" />
                  <span className="cf-product__link">
                    <LinkIcon />
                    商品{index + 1}に紐づく画像
                  </span>
                  <div className="cf-product__menu" ref={openMenu === index ? menuRef : undefined}>
                    <button
                      type="button"
                      className="cf-iconbtn"
                      title="メニュー"
                      aria-label="商品メニュー"
                      aria-expanded={openMenu === index}
                      onClick={() => setOpenMenu((cur) => (cur === index ? null : index))}
                      disabled={busy}
                    >
                      <DotsIcon size={16} />
                    </button>
                    {openMenu === index && (
                      <div className="cf-menu" role="menu">
                        <button
                          type="button"
                          role="menuitem"
                          onClick={() => {
                            onClearProduct(index)
                            setOpenMenu(null)
                          }}
                        >
                          内容をクリア
                        </button>
                        {products.length > 1 && (
                          <button
                            type="button"
                            role="menuitem"
                            className="cf-menu__danger"
                            onClick={() => {
                              onRemoveProduct(index)
                              setOpenMenu(null)
                            }}
                          >
                            この商品ブロックを削除
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <div className="cf-product__body">
                  <DetailImagePicker
                    index={index}
                    files={product.files}
                    images={product.images}
                    disabled={busy}
                    onAdd={(files) => onDetailAdd(index, files)}
                    onRemoveFile={(fileIndex) => onDetailRemoveFile(index, fileIndex)}
                    onRemoveStored={onRemoveStoredImage}
                  />
                  <div className="cf-product__right">
                    <h4>抽出される商品情報</h4>
                    <p className="cf-section__note" style={{ margin: '0 0 10px' }}>
                      画像解析後に自動入力されます（手入力もできます）。
                    </p>
                    <div className="cf-inline-field">
                      <label htmlFor={`mk-${product.key}`}>メーカー</label>
                      <input
                        id={`mk-${product.key}`}
                        className="cf-input"
                        placeholder="画像解析後に自動入力"
                        value={product.manufacturer}
                        onChange={(e) => onProductChange(index, { manufacturer: e.target.value })}
                      />
                    </div>
                    <div className="cf-inline-field">
                      <label htmlFor={`nm-${product.key}`}>商品名</label>
                      <input
                        id={`nm-${product.key}`}
                        className="cf-input"
                        placeholder="画像解析後に自動入力"
                        value={product.product_name}
                        onChange={(e) => onProductChange(index, { product_name: e.target.value })}
                      />
                    </div>
                    <div className="cf-inline-field">
                      <label htmlFor={`mn-${product.key}`}>型式</label>
                      <input
                        id={`mn-${product.key}`}
                        className="cf-input"
                        placeholder="画像解析後に自動入力"
                        value={product.model_number}
                        onChange={(e) => onProductChange(index, { model_number: e.target.value })}
                      />
                    </div>
                    <div className="cf-inline-field">
                      <label htmlFor={`cd-${product.key}`}>状態</label>
                      <select
                        id={`cd-${product.key}`}
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
            )
          })}
        </Section>
      </div>

      <div className="cf-actionrow" style={{ marginTop: 22 }}>
        <button
          type="button"
          className="cf-btn cf-btn--navy cf-btn--lg"
          onClick={onAnalyze}
          disabled={busy}
        >
          {busy ? '処理中…' : '画像を解析して情報入力'}
        </button>
        <button
          type="button"
          className="cf-btn cf-btn--outline cf-btn--lg"
          onClick={onSaveDraft}
          disabled={busy}
        >
          下書き保存
        </button>
      </div>
    </>
  )
}
