import { createContext, useContext } from 'react'

export interface NavigateOptions {
  to: string
  params?: Record<string, string>
  search?: Record<string, unknown>
}

export interface RouterLocation {
  pathname: string
  search: string
}

export interface RouterContextValue {
  location: RouterLocation
  navigate: (options: NavigateOptions) => Promise<void>
}

export function buildHref(
  to: string,
  params?: Record<string, string>,
  search?: Record<string, unknown>,
): string {
  let path = to
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      path = path.replace(`$${key}`, encodeURIComponent(value))
    }
  }
  if (search) {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(search)) {
      if (value !== undefined && value !== null && value !== false) {
        query.set(key, String(value))
      }
    }
    const qs = query.toString()
    if (qs) {
      path = `${path}?${qs}`
    }
  }
  return path
}

export const RouterContext = createContext<RouterContextValue>({
  location: { pathname: '/', search: '' },
  navigate: async () => {},
})

export function useNavigate() {
  return useContext(RouterContext).navigate
}

export function useLocation() {
  return useContext(RouterContext).location
}
