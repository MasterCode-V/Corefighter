import type { ReactNode } from 'react'
import logo from '../assets/logo-navy.png'
import { ChevronLeft, ChevronRight } from './Icons'

/* ------------------------------------------------------------------ header */

function HeaderDeco() {
  const slash = (color: string, width: number) => (
    <span
      style={{
        display: 'block',
        width,
        height: 12,
        background: color,
        transform: 'skewX(-26deg)',
        borderRadius: 1,
      }}
    />
  )
  return (
    <div className="cf-header__deco">
      <div
        style={{
          position: 'absolute',
          right: 0,
          bottom: 2,
          display: 'flex',
          alignItems: 'flex-end',
          gap: 4,
          width: '100%',
          justifyContent: 'flex-end',
        }}
      >
        {slash('rgba(255,255,255,0.20)', 7)}
        {slash('#3f5eab', 7)}
        {slash('rgba(255,255,255,0.85)', 5)}
        {slash('#2c4a99', 9)}
        {slash('#ffd400', 7)}
        <span
          style={{
            display: 'block',
            height: 3,
            width: 'clamp(80px, 34vw, 330px)',
            background: 'var(--red)',
            marginLeft: 2,
            marginBottom: 1,
          }}
        />
      </div>
    </div>
  )
}

export type HeaderProps = {
  accountLabel: string
  onLogout: () => void
  onHome: () => void
  showAdmin?: boolean
  adminActive?: boolean
  onAdmin?: () => void
}

export function AppHeader({
  accountLabel,
  onLogout,
  onHome,
  showAdmin,
  adminActive,
  onAdmin,
}: HeaderProps) {
  return (
    <header className="cf-header">
      <HeaderDeco />
      <div className="cf-header__inner">
        <button className="cf-logo" type="button" onClick={onHome} title="記事一覧へ">
          <img src={logo} alt="CORE FIGHTER" />
        </button>
        <div className="cf-header__right">
          <span className="cf-header__account">{accountLabel}</span>
          {showAdmin && (
            <button
              type="button"
              className={`cf-chip-admin${adminActive ? ' is-active' : ''}`}
              onClick={onAdmin}
            >
              管理画面
            </button>
          )}
          <button type="button" className="cf-btn-logout" onClick={onLogout}>
            ログアウト
          </button>
        </div>
      </div>
    </header>
  )
}

/* ---------------------------------------------------------------- back bar */

export function BackBar({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <div className="cf-backbar">
      <div className="cf-backbar__inner">
        <button type="button" className="cf-btn-back" onClick={onClick}>
          <ChevronLeft size={13} />
          {label}
        </button>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------- stepper */

export function Stepper({
  steps,
  current,
  onJump,
}: {
  steps: string[]
  current: number
  onJump?: (index: number) => void
}) {
  return (
    <div className="cf-steps">
      {steps.map((label, i) => {
        const state = i === current ? 'is-current' : i < current ? 'is-done' : ''
        return (
          <div key={label} style={{ display: 'contents' }}>
            <button
              type="button"
              className={`cf-step ${state}`}
              onClick={() => (i < current && onJump ? onJump(i) : undefined)}
              disabled={i >= current || !onJump}
            >
              <span className="cf-step__num">{i + 1}</span>
              {label}
            </button>
            {i < steps.length - 1 && <span className="cf-step__line" />}
          </div>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------ panel pieces */

export function PanelTitle({
  title,
  sub,
  rule = true,
  double = false,
  action,
}: {
  title: string
  sub?: string
  rule?: boolean
  double?: boolean
  action?: ReactNode
}) {
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div className="cf-title">
            <span className={`cf-title__mark${double ? ' cf-title__mark--double' : ''}`} />
            <h2>{title}</h2>
          </div>
          {sub && <p className="cf-title__sub">{sub}</p>}
        </div>
        {action}
      </div>
      {rule && <div className="cf-title-rule" />}
    </>
  )
}

export function Section({
  num,
  label,
  note,
  action,
  children,
}: {
  /** Omit to hide the navy number badge (wizard stepper already shows progress). */
  num?: number
  label: string
  note?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="cf-section">
      <div className="cf-section__head">
        <span className={`cf-section__title${num !== undefined ? ' is-numbered' : ''}`}>
          {num !== undefined && <span className="cf-section__num">{num}</span>}
          <span className="cf-section__label">{label}</span>
        </span>
        <span className="cf-section__spacer" />
        {action}
      </div>
      {note && <p className="cf-section__note">{note}</p>}
      {children}
    </section>
  )
}

export function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string
  required?: boolean
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="cf-field">
      <span className="cf-field__label">
        {label}
        {required && <span className="req">必須</span>}
      </span>
      {children}
      {hint && <span className="cf-field__hint">{hint}</span>}
    </label>
  )
}

/* ------------------------------------------------------------------ toggle */

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  label?: string
}) {
  return (
    <span className="cf-toggle">
      {label && <span>{label}</span>}
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label || 'toggle'}
        className={`cf-toggle__track${checked ? ' is-on' : ''}`}
        onClick={() => onChange(!checked)}
      >
        <span className="cf-toggle__knob" />
      </button>
    </span>
  )
}

/* ------------------------------------------------------------------ modals */

export function Modal({
  title,
  children,
  onClose,
  wide,
}: {
  title: string
  children: ReactNode
  onClose: () => void
  wide?: boolean
}) {
  return (
    <div className="cf-modal-backdrop" onClick={onClose} role="presentation">
      <div
        className={`cf-modal${wide ? ' cf-modal--wide' : ''}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <PanelTitle title={title} />
        {children}
      </div>
    </div>
  )
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = '削除する',
  onConfirm,
  onCancel,
  busy,
}: {
  title: string
  message: string
  confirmLabel?: string
  onConfirm: () => void
  onCancel: () => void
  busy?: boolean
}) {
  return (
    <div className="cf-modal-backdrop" onClick={onCancel} role="presentation">
      <div className="cf-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <h3>{title}</h3>
        <p>{message}</p>
        <div className="cf-modal__actions">
          <button type="button" className="cf-btn cf-btn--ghost" onClick={onCancel} disabled={busy}>
            キャンセル
          </button>
          <button type="button" className="cf-btn cf-btn--danger" onClick={onConfirm} disabled={busy}>
            {busy ? '処理中…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------- pagination */

export function Pager({
  page,
  pageCount,
  onChange,
}: {
  page: number
  pageCount: number
  onChange: (page: number) => void
}) {
  if (pageCount <= 1) return null
  const pages: number[] = []
  const from = Math.max(1, Math.min(page - 2, pageCount - 4))
  const to = Math.min(pageCount, from + 4)
  for (let i = from; i <= to; i++) pages.push(i)
  return (
    <nav className="cf-pager" aria-label="ページ送り">
      <button type="button" onClick={() => onChange(page - 1)} disabled={page <= 1} aria-label="前へ">
        <ChevronLeft size={13} />
      </button>
      {pages.map((p) => (
        <button
          key={p}
          type="button"
          className={p === page ? 'is-active' : ''}
          onClick={() => onChange(p)}
          aria-current={p === page ? 'page' : undefined}
        >
          {p}
        </button>
      ))}
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page >= pageCount}
        aria-label="次へ"
      >
        <ChevronRight size={13} />
      </button>
    </nav>
  )
}

/* ------------------------------------------------------------------ banner */

export function Banner({
  kind = 'error',
  children,
}: {
  kind?: 'error' | 'info' | 'ok'
  children: ReactNode
}) {
  return <div className={`cf-banner cf-banner--${kind}`}>{children}</div>
}
