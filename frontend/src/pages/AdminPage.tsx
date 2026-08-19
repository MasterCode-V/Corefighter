import { useCallback, useEffect, useState } from 'react'
import {
  createPersona,
  createPurchaseMethod,
  createStore,
  createUser,
  deletePersona,
  deletePurchaseMethod,
  deleteUser,
  listPersonas,
  listPurchaseMethods,
  listUsers,
  updatePersona,
  updatePurchaseMethod,
  updateStore,
  type Persona,
  type PurchaseMethod,
  type Store,
  type User,
} from '../api'
import { explainWorkflowError, roleLabel } from '../lib/format'
import { PlusIcon, TrashIcon, UserIcon } from '../ui/Icons'
import { Banner, ConfirmDialog, Field, PanelTitle, Toggle } from '../ui/Layout'

const ROLE_OPTIONS = [
  { value: 'STORE_STAFF', label: '編集者' },
  { value: 'STORE_MANAGER', label: '店舗管理者' },
  { value: 'ADMIN', label: '管理者' },
]

type PersonaDraft = {
  id: string | null
  name: string
  system_prompt: string
  is_active: boolean
}

const NEW_PERSONA: PersonaDraft = { id: null, name: '', system_prompt: '', is_active: true }

type StoreDraft = {
  id: string | null
  name: string
  code: string
  sort_order: number
  is_active: boolean
}

type MethodDraft = {
  id: string | null
  label: string
  sort_order: number
  is_active: boolean
  requires_area: boolean
  linked_store_id: string
}

const NEW_STORE: StoreDraft = { id: null, name: '', code: '', sort_order: 0, is_active: true }
const NEW_METHOD: MethodDraft = {
  id: null,
  label: '',
  sort_order: 0,
  is_active: true,
  requires_area: false,
  linked_store_id: '',
}

export default function AdminPage({
  token,
  currentUser,
  stores,
  onPersonasChanged,
  onStoresChanged,
}: {
  token: string
  currentUser: User
  stores: Store[]
  onPersonasChanged: () => void
  onStoresChanged: () => void
}) {
  const [personas, setPersonas] = useState<Persona[]>([])
  const [methods, setMethods] = useState<PurchaseMethod[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [draft, setDraft] = useState<PersonaDraft>(NEW_PERSONA)
  const [storeDraft, setStoreDraft] = useState<StoreDraft>(NEW_STORE)
  const [methodDraft, setMethodDraft] = useState<MethodDraft>(NEW_METHOD)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  const [account, setAccount] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'STORE_STAFF',
    store_id: '',
    personaIds: [] as string[],
  })

  const [personaToDelete, setPersonaToDelete] = useState<Persona | null>(null)
  const [userToDelete, setUserToDelete] = useState<User | null>(null)

  const load = useCallback(async () => {
    setError('')
    try {
      const [p, u, m] = await Promise.all([
        listPersonas(token, true),
        listUsers(token),
        listPurchaseMethods(token),
      ])
      setPersonas(p)
      setUsers(u)
      setMethods(m)
      setDraft((d) => (d.id ? d : p[0] ? toDraft(p[0]) : NEW_PERSONA))
    } catch (err) {
      setError(explainWorkflowError(err, '管理データの取得に失敗しました'))
    }
  }, [token])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!account.store_id && stores.length) {
      setAccount((a) => ({ ...a, store_id: stores[0].id }))
    }
  }, [stores, account.store_id])

  function toDraft(p: Persona): PersonaDraft {
    return {
      id: p.id,
      name: p.name,
      system_prompt: p.system_prompt || p.description || '',
      is_active: p.is_active !== false,
    }
  }

  function toStoreDraft(s: Store): StoreDraft {
    return {
      id: s.id,
      name: s.name,
      code: s.code,
      sort_order: s.sort_order ?? 0,
      is_active: s.is_active !== false,
    }
  }

  function toMethodDraft(m: PurchaseMethod): MethodDraft {
    return {
      id: m.id,
      label: m.label,
      sort_order: m.sort_order,
      is_active: m.is_active !== false,
      requires_area: m.requires_area,
      linked_store_id: m.linked_store_id || '',
    }
  }

  async function saveStore() {
    if (!storeDraft.name.trim() || !storeDraft.code.trim()) {
      setError('店舗名とコードを入力してください')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      if (storeDraft.id) {
        await updateStore(token, storeDraft.id, {
          name: storeDraft.name.trim(),
          sort_order: storeDraft.sort_order,
          is_active: storeDraft.is_active,
        })
        setNotice('店舗を更新しました。')
      } else {
        const created = await createStore(token, {
          name: storeDraft.name.trim(),
          code: storeDraft.code.trim(),
          sort_order: storeDraft.sort_order,
        })
        setStoreDraft(toStoreDraft(created))
        setNotice('店舗を作成しました。')
      }
      onStoresChanged()
      await load()
    } catch (err) {
      setError(explainWorkflowError(err, '店舗の保存に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  async function saveMethod() {
    if (!methodDraft.label.trim()) {
      setError('買取方法名を入力してください')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const payload = {
        label: methodDraft.label.trim(),
        sort_order: methodDraft.sort_order,
        is_active: methodDraft.is_active,
        requires_area: methodDraft.requires_area,
        linked_store_id: methodDraft.linked_store_id || null,
      }
      if (methodDraft.id) {
        await updatePurchaseMethod(token, methodDraft.id, payload)
        setNotice('買取方法を更新しました。')
      } else {
        const created = await createPurchaseMethod(token, payload)
        setMethodDraft(toMethodDraft(created))
        setNotice('買取方法を作成しました。')
      }
      onStoresChanged()
      await load()
    } catch (err) {
      setError(explainWorkflowError(err, '買取方法の保存に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  async function confirmMethodDelete(id: string) {
    if (!window.confirm('この買取方法を削除しますか？')) return
    setBusy(true)
    try {
      await deletePurchaseMethod(token, id)
      if (methodDraft.id === id) setMethodDraft(NEW_METHOD)
      onStoresChanged()
      await load()
      setNotice('買取方法を削除しました。')
    } catch (err) {
      setError(explainWorkflowError(err, '買取方法の削除に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  async function savePersona() {
    if (!draft.name.trim()) {
      setError('人格名を入力してください')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      if (draft.id) {
        await updatePersona(token, draft.id, {
          name: draft.name.trim(),
          system_prompt: draft.system_prompt,
          is_active: draft.is_active,
        })
        setNotice('AI人格を更新しました。')
      } else {
        const created = await createPersona(token, {
          name: draft.name.trim(),
          system_prompt: draft.system_prompt,
        })
        setDraft(toDraft(created))
        setNotice('AI人格を作成しました。')
      }
      await load()
      onPersonasChanged()
    } catch (err) {
      setError(explainWorkflowError(err, 'AI人格の保存に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  async function confirmPersonaDelete() {
    if (!personaToDelete) return
    setBusy(true)
    try {
      await deletePersona(token, personaToDelete.id)
      if (draft.id === personaToDelete.id) setDraft(NEW_PERSONA)
      setPersonaToDelete(null)
      await load()
      onPersonasChanged()
    } catch (err) {
      setError(explainWorkflowError(err, 'AI人格の削除に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  async function issueAccount() {
    if (!account.email.trim() || account.password.length < 8) {
      setError('メールアドレスと8文字以上のパスワードを入力してください')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await createUser(token, {
        email: account.email.trim(),
        password: account.password,
        full_name: account.full_name.trim(),
        role: account.role,
        store_id: account.role === 'ADMIN' ? null : account.store_id || null,
        allowed_persona_ids: account.personaIds,
      })
      setAccount({
        full_name: '',
        email: '',
        password: '',
        role: 'STORE_STAFF',
        store_id: stores[0]?.id || '',
        personaIds: [],
      })
      setNotice('アカウントを発行しました。')
      await load()
    } catch (err) {
      setError(explainWorkflowError(err, 'アカウントの発行に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  async function confirmUserDelete() {
    if (!userToDelete) return
    setBusy(true)
    try {
      await deleteUser(token, userToDelete.id)
      setUserToDelete(null)
      await load()
    } catch (err) {
      setError(explainWorkflowError(err, 'アカウントの削除に失敗しました'))
    } finally {
      setBusy(false)
    }
  }

  function personaSummary(u: User) {
    const list = u.allowed_personas || []
    if (!list.length) return 'すべての AI 人格'
    if (list.length === 1) return list[0].name
    return `${list[0].name} … 他 ${list.length - 1} 人`
  }

  return (
    <div className="cf-page cf-page--wide">
      {error && <Banner kind="error">{error}</Banner>}
      {notice && <Banner kind="ok">{notice}</Banner>}

      <div className="cf-panel">
        <PanelTitle title="AI 人格管理" />
        <div className="cf-split">
          <div className="cf-subcard">
            <h3 className="cf-subcard__title">AI 人格一覧</h3>
            <table className="cf-table">
              <thead>
                <tr>
                  <th style={{ width: '60%' }}>人格名</th>
                  <th>ステータス</th>
                  <th style={{ width: 46 }} aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {personas.length === 0 && (
                  <tr>
                    <td colSpan={3} style={{ color: 'var(--muted)' }}>
                      AI人格が登録されていません。
                    </td>
                  </tr>
                )}
                {personas.map((p) => (
                  <tr
                    key={p.id}
                    className={`is-clickable${draft.id === p.id ? ' is-selected' : ''}`}
                    onClick={() => setDraft(toDraft(p))}
                  >
                    <td>
                      <div className="cf-table__cellflex">
                        <span className="cf-table__avatar">
                          <UserIcon />
                        </span>
                        <span className="cf-table__name">{p.name}</span>
                      </div>
                    </td>
                    <td>
                      <span
                        className={`cf-badge ${
                          p.is_active === false ? 'cf-badge--outline-gray' : 'cf-badge--outline-green'
                        }`}
                      >
                        {p.is_active === false ? '停止' : '有効'}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="cf-iconbtn"
                        aria-label={`${p.name} を削除`}
                        onClick={(e) => {
                          e.stopPropagation()
                          setPersonaToDelete(p)
                        }}
                      >
                        <TrashIcon />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="cf-subcard">
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 12,
              }}
            >
              <h3 className="cf-subcard__title" style={{ margin: 0 }}>
                AI 人格詳細
              </h3>
              <button
                type="button"
                className="cf-btn cf-btn--navy cf-btn--sm"
                onClick={() => setDraft(NEW_PERSONA)}
              >
                <PlusIcon />
                新規人格を作成
              </button>
            </div>
            <Field label="人格名">
              <input
                className="cf-input"
                value={draft.name}
                placeholder="例：パワトレおじさん"
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </Field>
            <Field
              label="人格プロンプト"
              hint="この人格が記事を書くときの口調・視点・禁止事項などを指定します。"
            >
              <textarea
                className="cf-textarea"
                style={{ minHeight: 210 }}
                value={draft.system_prompt}
                onChange={(e) => setDraft({ ...draft, system_prompt: e.target.value })}
              />
            </Field>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 18,
                marginTop: 6,
              }}
            >
              <Toggle
                label="ステータス"
                checked={draft.is_active}
                onChange={(v) => setDraft({ ...draft, is_active: v })}
              />
              <button
                type="button"
                className="cf-btn cf-btn--navy"
                onClick={savePersona}
                disabled={busy}
              >
                保存する
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="cf-panel">
        <PanelTitle title="店舗管理" sub="掲載店舗の追加・並び順・有効/無効" />
        <div className="cf-split">
          <div className="cf-subcard">
            <h3 className="cf-subcard__title">店舗一覧</h3>
            <table className="cf-table">
              <thead>
                <tr>
                  <th>店舗名</th>
                  <th style={{ width: 70 }}>順序</th>
                  <th style={{ width: 80 }}>状態</th>
                </tr>
              </thead>
              <tbody>
                {stores.map((s) => (
                  <tr
                    key={s.id}
                    className={`is-clickable${storeDraft.id === s.id ? ' is-selected' : ''}`}
                    onClick={() => setStoreDraft(toStoreDraft(s))}
                  >
                    <td>
                      <div className="cf-table__name">{s.name}</div>
                      <div className="cf-table__sub">{s.code}</div>
                    </td>
                    <td>{s.sort_order ?? 0}</td>
                    <td>
                      <span
                        className={`cf-badge ${
                          s.is_active === false ? 'cf-badge--outline-gray' : 'cf-badge--outline-green'
                        }`}
                      >
                        {s.is_active === false ? '停止' : '有効'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="cf-subcard">
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 12,
              }}
            >
              <h3 className="cf-subcard__title" style={{ margin: 0 }}>
                店舗詳細
              </h3>
              <button
                type="button"
                className="cf-btn cf-btn--navy cf-btn--sm"
                onClick={() => setStoreDraft(NEW_STORE)}
              >
                <PlusIcon />
                新規店舗
              </button>
            </div>
            <Field label="店舗名">
              <input
                className="cf-input"
                value={storeDraft.name}
                onChange={(e) => setStoreDraft({ ...storeDraft, name: e.target.value })}
              />
            </Field>
            <Field label="コード" hint="英数字（作成後は変更不可）">
              <input
                className="cf-input"
                value={storeDraft.code}
                disabled={Boolean(storeDraft.id)}
                onChange={(e) => setStoreDraft({ ...storeDraft, code: e.target.value })}
              />
            </Field>
            <Field label="表示順">
              <input
                className="cf-input"
                type="number"
                value={storeDraft.sort_order}
                onChange={(e) =>
                  setStoreDraft({ ...storeDraft, sort_order: Number(e.target.value) || 0 })
                }
              />
            </Field>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 18, marginTop: 6 }}>
              <Toggle
                label="有効"
                checked={storeDraft.is_active}
                onChange={(v) => setStoreDraft({ ...storeDraft, is_active: v })}
              />
              <button
                type="button"
                className="cf-btn cf-btn--navy"
                onClick={saveStore}
                disabled={busy}
              >
                保存する
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="cf-panel">
        <PanelTitle
          title="買取方法管理"
          sub="出張→デリパワ、宅配→宅配買取 など掲載店舗の自動紐付け"
        />
        <div className="cf-split">
          <div className="cf-subcard">
            <h3 className="cf-subcard__title">買取方法一覧</h3>
            <table className="cf-table">
              <thead>
                <tr>
                  <th>方法名</th>
                  <th>紐付け店舗</th>
                  <th style={{ width: 46 }} aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {methods.map((m) => {
                  const linked = stores.find((s) => s.id === m.linked_store_id)
                  return (
                    <tr
                      key={m.id}
                      className={`is-clickable${methodDraft.id === m.id ? ' is-selected' : ''}`}
                      onClick={() => setMethodDraft(toMethodDraft(m))}
                    >
                      <td>
                        <div className="cf-table__name">{m.label}</div>
                        {m.requires_area && (
                          <div className="cf-table__sub">買取地区入力あり</div>
                        )}
                      </td>
                      <td>{linked?.name || '（店舗選択）'}</td>
                      <td>
                        <button
                          type="button"
                          className="cf-iconbtn"
                          aria-label={`${m.label} を削除`}
                          onClick={(e) => {
                            e.stopPropagation()
                            void confirmMethodDelete(m.id)
                          }}
                        >
                          <TrashIcon />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="cf-subcard">
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 12,
              }}
            >
              <h3 className="cf-subcard__title" style={{ margin: 0 }}>
                買取方法詳細
              </h3>
              <button
                type="button"
                className="cf-btn cf-btn--navy cf-btn--sm"
                onClick={() => setMethodDraft(NEW_METHOD)}
              >
                <PlusIcon />
                新規追加
              </button>
            </div>
            <Field label="方法名">
              <input
                className="cf-input"
                placeholder="例：出張"
                value={methodDraft.label}
                onChange={(e) => setMethodDraft({ ...methodDraft, label: e.target.value })}
              />
            </Field>
            <Field label="表示順">
              <input
                className="cf-input"
                type="number"
                value={methodDraft.sort_order}
                onChange={(e) =>
                  setMethodDraft({ ...methodDraft, sort_order: Number(e.target.value) || 0 })
                }
              />
            </Field>
            <Field label="掲載店舗（自動紐付け）" hint="未設定の場合は記事作成時に店舗を選択">
              <select
                className="cf-select"
                value={methodDraft.linked_store_id}
                onChange={(e) =>
                  setMethodDraft({ ...methodDraft, linked_store_id: e.target.value })
                }
              >
                <option value="">（選択式 — 店頭など）</option>
                {stores.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 18, marginTop: 6 }}>
              <Toggle
                label="買取地区入力"
                checked={methodDraft.requires_area}
                onChange={(v) => setMethodDraft({ ...methodDraft, requires_area: v })}
              />
              <Toggle
                label="有効"
                checked={methodDraft.is_active}
                onChange={(v) => setMethodDraft({ ...methodDraft, is_active: v })}
              />
              <button
                type="button"
                className="cf-btn cf-btn--navy"
                onClick={saveMethod}
                disabled={busy}
              >
                保存する
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="cf-panel">
        <PanelTitle title="アカウント管理" />
        <div className="cf-split cf-split--narrow-left">
          <div className="cf-subcard">
            <h3 className="cf-subcard__title">新規アカウント発行</h3>
            <Field label="アカウント名">
              <input
                className="cf-input"
                placeholder="テスト太郎"
                value={account.full_name}
                onChange={(e) => setAccount({ ...account, full_name: e.target.value })}
              />
            </Field>
            <Field label="メールアドレス">
              <input
                className="cf-input"
                type="email"
                placeholder="test@test.com"
                value={account.email}
                onChange={(e) => setAccount({ ...account, email: e.target.value })}
              />
            </Field>
            <Field label="パスワード" hint="8文字以上">
              <input
                className="cf-input"
                type="password"
                placeholder="8文字以上で入力"
                value={account.password}
                onChange={(e) => setAccount({ ...account, password: e.target.value })}
              />
            </Field>
            <Field label="権限">
              <select
                className="cf-select"
                value={account.role}
                onChange={(e) => setAccount({ ...account, role: e.target.value })}
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </Field>
            {account.role !== 'ADMIN' && (
              <Field label="所属店舗">
                <select
                  className="cf-select"
                  value={account.store_id}
                  onChange={(e) => setAccount({ ...account, store_id: e.target.value })}
                >
                  {stores.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field label="利用可能な AI 人格" hint="未選択の場合はすべての人格を利用できます。">
              <div className="cf-checklist">
                {personas.map((p) => (
                  <label className="cf-check" key={p.id}>
                    <input
                      type="checkbox"
                      checked={account.personaIds.includes(p.id)}
                      onChange={(e) =>
                        setAccount({
                          ...account,
                          personaIds: e.target.checked
                            ? [...account.personaIds, p.id]
                            : account.personaIds.filter((id) => id !== p.id),
                        })
                      }
                    />
                    {p.name}
                  </label>
                ))}
                {personas.length === 0 && (
                  <span style={{ color: 'var(--muted)', fontSize: 12 }}>
                    AI人格が未登録です
                  </span>
                )}
              </div>
            </Field>
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: 16 }}>
              <button
                type="button"
                className="cf-btn cf-btn--navy"
                onClick={issueAccount}
                disabled={busy}
              >
                アカウントを発行
              </button>
            </div>
          </div>

          <div className="cf-subcard">
            <h3 className="cf-subcard__title">アカウント一覧</h3>
            <table className="cf-table">
              <thead>
                <tr>
                  <th>アカウント名／メールアドレス</th>
                  <th style={{ width: 110 }}>権限</th>
                  <th>利用可能な AI 人格</th>
                  <th style={{ width: 46 }} aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <div className="cf-table__name">{u.full_name || '(名称未設定)'}</div>
                      <div className="cf-table__sub">{u.email}</div>
                    </td>
                    <td>
                      <span className="cf-badge cf-badge--navyline">{roleLabel(u.role)}</span>
                    </td>
                    <td style={{ color: 'var(--ink)' }}>{personaSummary(u)}</td>
                    <td>
                      <button
                        type="button"
                        className="cf-iconbtn"
                        aria-label={`${u.email} を削除`}
                        disabled={u.id === currentUser.id}
                        title={
                          u.id === currentUser.id
                            ? 'ログイン中のアカウントは削除できません'
                            : 'このアカウントを削除'
                        }
                        onClick={() => setUserToDelete(u)}
                      >
                        <TrashIcon />
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{ color: 'var(--muted)' }}>
                      アカウントがありません。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {personaToDelete && (
        <ConfirmDialog
          title="AI人格を削除しますか？"
          message={`「${personaToDelete.name}」を削除します。この人格を使った過去の記事は残ります。`}
          onConfirm={confirmPersonaDelete}
          onCancel={() => setPersonaToDelete(null)}
          busy={busy}
        />
      )}

      {userToDelete && (
        <ConfirmDialog
          title="アカウントを削除しますか？"
          message={`「${userToDelete.full_name || userToDelete.email}」を削除します。この操作は取り消せません。`}
          onConfirm={confirmUserDelete}
          onCancel={() => setUserToDelete(null)}
          busy={busy}
        />
      )}
    </div>
  )
}
