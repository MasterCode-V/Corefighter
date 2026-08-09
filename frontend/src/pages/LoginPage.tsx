import { useState, type FormEvent } from 'react'
import logo from '../assets/logo-navy.png'
import { Banner } from '../ui/Layout'

export default function LoginPage({
  onSubmit,
}: {
  onSubmit: (email: string, password: string) => Promise<void>
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await onSubmit(email.trim(), password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ログインに失敗しました')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="cf-login">
      <form className="cf-login__card" onSubmit={submit}>
        <img className="cf-login__logo" src={logo} alt="CORE FIGHTER" />
        {error && <Banner kind="error">{error}</Banner>}
        <label className="cf-field">
          <span className="cf-field__label">メールアドレス</span>
          <input
            className="cf-input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            placeholder="admin@hprn.jp"
            required
          />
        </label>
        <label className="cf-field">
          <span className="cf-field__label">パスワード</span>
          <input
            className="cf-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <button className="cf-login__submit" type="submit" disabled={busy}>
          {busy ? 'ログイン中…' : 'ログイン'}
        </button>
      </form>
    </div>
  )
}
