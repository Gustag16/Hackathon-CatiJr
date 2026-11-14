import { createContext, useContext } from 'react'
import type { User } from './interfaces/userInterface'

export const AuthContext = createContext<{
  user: User | null
  loading: boolean
  refresh: () => Promise<void>
}>({
  user: null,
  loading: true,
  refresh: async () => {},
})

export const useAuth = () => useContext(AuthContext)
