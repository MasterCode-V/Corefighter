import { useCallback, useEffect, useState } from 'react'
import {
  listPersonas,
  listStores,
  listWordpressCategories,
  login as apiLogin,
  me,
  type Persona,
  type Store,
  type User,
} from './api'
import { useRoute } from './lib/router'
import { explainWorkflowError, roleLabel } from './lib/format'
import AdminPage from './pages/AdminPage'
import ArticleListPage from './pages/ArticleListPage'
import GeneratePage from './pages/GeneratePage'
import LoginPage from './pages/LoginPage'
import OpsPanel from './OpsPanel'
import { AppHeader, BackBar, Banner } from './ui/Layout'

const TOKEN_KEY = 'cf_token'

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<User | null>(null)
  const [stores, setStores] = useState<Store[]>([])
  const [personas, setPersonas] = useState<Persona[]>([])
  const [wpCategories, setWpCategories] = useState<Array<{ id: number; name: string }>>([])
  const [bootError, setBootError] = useState('')
  const [route, navigate] = useRoute()

  const loadPersonas = useCallback(async () => {
    if (!token) return
    try {
      setPersonas(await listPersonas(token))
    } catch {
      /* non fatal */
    }
  }, [token])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    ;(async () => {
      try {
        const current = await me(token)
        if (cancelled) return
        setUser(current)
        const [s, p, cats] = await Promise.all([
          listStores(token),
          listPersonas(token),
          listWordpressCategories(token, true).catch(() => []),
        ])
        if (cancelled) return
        setStores(s)
        setPersonas(p)
        setWpCategories(cats)
      } catch (err) {
        if (cancelled) return
        localStorage.removeItem(TOKEN_KEY)
        setToken(null)
        setUser(null)
        setBootError(explainWorkflowError(err, 'セッションの有効期限が切れました'))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token])

  async function handleLogin(email: string, password: string) {
    const result = await apiLogin(email, password)
    localStorage.setItem(TOKEN_KEY, result.access_token)
    setBootError('')
    setToken(result.access_token)
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
    navigate({ name: 'articles' })
  }

  if (!token || !user) {
    return (
      <>
        {bootError && (
          <div style={{ maxWidth: 400, margin: '20px auto -10px' }}>
            <Banner kind="error">{bootError}</Banner>
          </div>
        )}
        <LoginPage onSubmit={handleLogin} />
      </>
    )
  }

  const isAdmin = user.role === 'ADMIN'
  const accountLabel = `${user.full_name || user.email}・${roleLabel(user.role)}`
  const showBack = route.name !== 'articles'

  return (
    <>
      <AppHeader
        accountLabel={accountLabel}
        onLogout={logout}
        onHome={() => navigate({ name: 'articles' })}
        showAdmin={isAdmin}
        adminActive={route.name === 'admin'}
        onAdmin={() => navigate({ name: 'admin' })}
      />

      {showBack && (
        <BackBar label="記事一覧へ戻る" onClick={() => navigate({ name: 'articles' })} />
      )}

      {route.name === 'articles' && (
        <ArticleListPage
          token={token}
          stores={stores}
          isAdmin={isAdmin}
          onCreate={() => navigate({ name: 'generate' })}
          onEdit={(articleId) => navigate({ name: 'generate', articleId })}
        />
      )}

      {route.name === 'generate' && (
        <GeneratePage
          key={route.articleId || 'new'}
          token={token}
          user={user}
          stores={stores}
          personas={personas}
          wpCategories={wpCategories}
          articleId={route.articleId}
          onGoOps={() => navigate({ name: 'ops' })}
          onGoList={() => navigate({ name: 'articles' })}
          onOpenArticle={(articleId) => navigate({ name: 'generate', articleId })}
        />
      )}

      {route.name === 'ops' && (
        <div className="cf-page">
          <OpsPanel
            token={token}
            stores={stores}
            onOpenArticle={(article) => navigate({ name: 'generate', articleId: article.id })}
          />
        </div>
      )}

      {route.name === 'admin' &&
        (isAdmin ? (
          <AdminPage
            token={token}
            currentUser={user}
            stores={stores}
            onPersonasChanged={loadPersonas}
          />
        ) : (
          <div className="cf-page">
            <Banner kind="error">この画面は管理者のみ利用できます。</Banner>
          </div>
        ))}
    </>
  )
}
