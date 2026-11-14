import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { User } from './domain';
import { api } from './api';
const AuthContext = createContext<{user:User|null; loading:boolean; refresh:()=>Promise<void>}>({user:null,loading:true,refresh:async()=>{}});
export function AuthProvider({children}:{children:ReactNode}) { const [user,setUser] = useState<User|null>(null); const [loading,setLoading] = useState(true); const refresh = async () => { try { setUser(await api<User>('/api/auth/me')); } catch { setUser(null); } finally {setLoading(false);} }; useEffect(() => {void refresh();},[]); return <AuthContext.Provider value={{user,loading,refresh}}>{children}</AuthContext.Provider>; }
export const useAuth = () => useContext(AuthContext);
