import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, setOnUnauthorized } from '../../api/api'
import { AuthContext } from '../../utils/authContext'
import type { User } from '../../utils/interfaces/userInterface'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const me = await api.getMe()
      setUser(me)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setOnUnauthorized(() => {
      setUser(null)
    })
    api
      .getMe()
      .then((me) => setUser(me))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
    return () => setOnUnauthorized(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}
