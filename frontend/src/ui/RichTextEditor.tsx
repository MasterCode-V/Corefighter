import { useCallback, useEffect, useRef } from 'react'

type RichTextEditorProps = {
  value: string
  onChange: (html: string) => void
  disabled?: boolean
  placeholder?: string
}

function exec(command: string, value?: string) {
  document.execCommand(command, false, value)
}

export default function RichTextEditor({
  value,
  onChange,
  disabled,
  placeholder,
}: RichTextEditorProps) {
  const ref = useRef<HTMLDivElement>(null)
  const lastValue = useRef(value)

  useEffect(() => {
    const el = ref.current
    if (!el || el.innerHTML === value) return
    if (document.activeElement === el) return
    el.innerHTML = value || ''
    lastValue.current = value
  }, [value])

  const emitChange = useCallback(() => {
    const el = ref.current
    if (!el) return
    const html = el.innerHTML
    if (html !== lastValue.current) {
      lastValue.current = html
      onChange(html)
    }
  }, [onChange])

  function insertLink() {
    const url = window.prompt('リンクURLを入力')
    if (!url) return
    exec('createLink', url)
    emitChange()
  }

  return (
    <div className={`cf-rte${disabled ? ' is-disabled' : ''}`}>
      <div className="cf-rte__toolbar" role="toolbar" aria-label="書式">
        <button
          type="button"
          className="cf-rte__btn"
          title="太字"
          disabled={disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            exec('bold')
            emitChange()
          }}
        >
          B
        </button>
        <button
          type="button"
          className="cf-rte__btn"
          title="小さい文字"
          disabled={disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            exec('fontSize', '2')
            emitChange()
          }}
        >
          小
        </button>
        <button
          type="button"
          className="cf-rte__btn"
          title="通常サイズ"
          disabled={disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            exec('fontSize', '3')
            emitChange()
          }}
        >
          中
        </button>
        <button
          type="button"
          className="cf-rte__btn"
          title="大きい文字"
          disabled={disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            exec('fontSize', '5')
            emitChange()
          }}
        >
          大
        </button>
        <button
          type="button"
          className="cf-rte__btn"
          title="リンク"
          disabled={disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={insertLink}
        >
          リンク
        </button>
        <button
          type="button"
          className="cf-rte__btn"
          title="箇条書き"
          disabled={disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            exec('insertUnorderedList')
            emitChange()
          }}
        >
          • リスト
        </button>
      </div>
      <div
        ref={ref}
        className="cf-rte__body"
        contentEditable={!disabled}
        role="textbox"
        aria-multiline="true"
        data-placeholder={placeholder}
        suppressContentEditableWarning
        onInput={emitChange}
        onBlur={emitChange}
      />
    </div>
  )
}
