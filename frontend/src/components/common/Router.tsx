import {
  useCallback,
  useEffect,
  useState,
  type AnchorHTMLAttributes,
  type MouseEvent,
  type ReactNode,
} from 'react'
import {
  buildHref,
  RouterContext,
  useNavigate,
  type NavigateOptions,
  type RouterLocation,
} from '../../utils/routerContext'

export function RouterProvider({ children }: { children: ReactNode }) {
  const [location, setLocation] = useState<RouterLocation>(() => ({
    pathname: window.location.pathname || '/',
    search: window.location.search || '',
  }))

  useEffect(() => {
    const onPopState = () => {
      setLocation({
        pathname: window.location.pathname || '/',
        search: window.location.search || '',
      })
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const navigate = useCallback(async (options: NavigateOptions) => {
    const href = buildHref(options.to, options.params, options.search)
    window.history.pushState({}, '', href)
    const [pathname, rawSearch = ''] = href.split('?')
    setLocation({
      pathname: pathname || '/',
      search: rawSearch ? `?${rawSearch}` : '',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <RouterContext.Provider value={{ location, navigate }}>
      {children}
    </RouterContext.Provider>
  )
}

export interface LinkProps
  extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> {
  to: string
  params?: Record<string, string>
  search?: Record<string, unknown>
}

export function Link({
  to,
  params,
  search,
  onClick,
  children,
  ...rest
}: LinkProps) {
  const navigate = useNavigate()
  const href = buildHref(to, params, search)

  const handleClick = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e)
    if (
      e.defaultPrevented ||
      e.button !== 0 ||
      e.metaKey ||
      e.altKey ||
      e.ctrlKey ||
      e.shiftKey
    ) {
      return
    }
    e.preventDefault()
    void navigate({ to, params, search })
  }

  return (
    <a href={href} onClick={handleClick} {...rest}>
      {children}
    </a>
  )
}
