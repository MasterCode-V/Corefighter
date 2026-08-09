import { useCallback, useEffect, useState } from 'react'

export type Route =
  | { name: 'articles' }
  | { name: 'generate'; articleId?: string }
  | { name: 'ops' }
  | { name: 'admin' }

function parse(hash: string): Route {
  const path = hash.replace(/^#\/?/, '').split('?')[0]
  const parts = path.split('/').filter(Boolean)
  if (parts[0] === 'generate') return { name: 'generate', articleId: parts[1] }
  if (parts[0] === 'ops') return { name: 'ops' }
  if (parts[0] === 'admin') return { name: 'admin' }
  return { name: 'articles' }
}

export function toHash(route: Route): string {
  if (route.name === 'generate') {
    return route.articleId ? `#/generate/${route.articleId}` : '#/generate'
  }
  return `#/${route.name}`
}

export function useRoute(): [Route, (route: Route) => void] {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash))

  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  const navigate = useCallback((next: Route) => {
    const hash = toHash(next)
    if (window.location.hash === hash) {
      setRoute(parse(hash))
      return
    }
    window.location.hash = hash
  }, [])

  return [route, navigate]
}
