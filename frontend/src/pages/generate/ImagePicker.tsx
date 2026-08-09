import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import type { PurchaseImage } from '../../api'
import { proxyImageUrl } from '../../lib/format'
import { ImageIcon, UploadIcon } from '../../ui/Icons'

export type PickerItem =
  | { kind: 'file'; file: File; url: string }
  | { kind: 'stored'; image: PurchaseImage; url: string }

function useItems(files: File[], images: PurchaseImage[]): PickerItem[] {
  const urls = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files])
  useEffect(() => () => urls.forEach((u) => URL.revokeObjectURL(u)), [urls])
  return [
    ...images.map((image) => ({
      kind: 'stored' as const,
      image,
      url: proxyImageUrl(image.url),
    })),
    ...files.map((file, i) => ({ kind: 'file' as const, file, url: urls[i] })),
  ]
}

function Thumbs({
  items,
  minSlots,
  onRemove,
}: {
  items: PickerItem[]
  minSlots: number
  onRemove: (item: PickerItem, index: number) => void
}) {
  const empties = Math.max(0, minSlots - items.length)
  return (
    <div className="cf-thumbs">
      {items.map((item, i) => (
        <div className="cf-thumb" key={item.kind === 'file' ? `f${i}` : item.image.id}>
          <img src={item.url} alt="" />
          <button
            type="button"
            className="cf-thumb__del"
            aria-label="この画像を削除"
            onClick={() => onRemove(item, i)}
          >
            ×
          </button>
        </div>
      ))}
      {Array.from({ length: empties }).map((_, i) => (
        <div className="cf-thumb cf-thumb--empty" key={`e${i}`}>
          <ImageIcon />
        </div>
      ))}
    </div>
  )
}

/** Large dashed dropzone used for the main (eye-catch) image. */
export function MainImagePicker({
  files,
  images,
  disabled,
  onAdd,
  onRemoveFile,
  onRemoveStored,
}: {
  files: File[]
  images: PurchaseImage[]
  disabled?: boolean
  onAdd: (files: File[]) => void
  onRemoveFile: (index: number) => void
  onRemoveStored: (image: PurchaseImage) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const items = useItems(files, images)

  function pick(list: FileList | null) {
    if (!list?.length) return
    onAdd(Array.from(list).filter((f) => f.type.startsWith('image/')))
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setOver(false)
    if (!disabled) pick(e.dataTransfer.files)
  }

  return (
    <div
      className={`cf-drop${over ? ' is-over' : ''}`}
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      <div className="cf-drop__title">
        <UploadIcon />
        商品の全体写真を追加
      </div>
      <p className="cf-drop__note">
        記事のアイキャッチ・買取品のまとめ画像として使用します。
        <br />
        複数商品の詳細情報の抽出には使用しません。
      </p>
      <button
        type="button"
        className="cf-btn cf-btn--outline"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
      >
        ファイルを選択
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => {
          pick(e.target.files)
          e.target.value = ''
        }}
      />
      {items.length > 0 && (
        <Thumbs
          items={items}
          minSlots={0}
          onRemove={(item, i) =>
            item.kind === 'file' ? onRemoveFile(i - images.length) : onRemoveStored(item.image)
          }
        />
      )}
    </div>
  )
}

/** Compact per-product picker shown inside each product block. */
export function DetailImagePicker({
  index,
  files,
  images,
  disabled,
  onAdd,
  onRemoveFile,
  onRemoveStored,
}: {
  index: number
  files: File[]
  images: PurchaseImage[]
  disabled?: boolean
  onAdd: (files: File[]) => void
  onRemoveFile: (index: number) => void
  onRemoveStored: (image: PurchaseImage) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const items = useItems(files, images)

  return (
    <div className="cf-product__left">
      <h4>商品{index + 1}の詳細画像</h4>
      <p>
        ラベル・型番・箱の接写を追加
        <br />
        この画像から商品{index + 1}の情報を抽出します
      </p>
      <div style={{ margin: '10px 0 8px' }}>
        <UploadIcon size={24} />
      </div>
      <button
        type="button"
        className="cf-btn cf-btn--outline cf-btn--sm"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
      >
        画像を選択
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => {
          const list = e.target.files
          if (list?.length) onAdd(Array.from(list).filter((f) => f.type.startsWith('image/')))
          e.target.value = ''
        }}
      />
      <Thumbs
        items={items}
        minSlots={2}
        onRemove={(item, i) =>
          item.kind === 'file' ? onRemoveFile(i - images.length) : onRemoveStored(item.image)
        }
      />
    </div>
  )
}
