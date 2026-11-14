import { useState, type ReactNode } from 'react'
import { api } from '../../api/api'
import { useAuth } from '../../utils/authContext'
import { Link } from './Router'
import { Button, Icon } from './Ui'

const CURRENT_YEAR = new Date().getFullYear()

export function Shell({ children }: { children: ReactNode }) {
  const { user, refresh } = useAuth()
  const [error, setError] = useState('')

  return (
    <>
      <header className="bg-header text-header-foreground">
        <div className="page-width flex min-h-20 flex-wrap items-center justify-between gap-4 py-4">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Icon name="bolt" className="h-7 w-7" />
            </span>
            <span className="text-xl font-extrabold">
              katchau
              <span className="ml-2 text-[10px] font-semibold uppercase tracking-[2px] text-slate-300">
                Leilões
              </span>
            </span>
          </Link>
          <nav className="flex items-center gap-3 text-xs">
            <Link to="/" className="mr-7 hidden font-bold text-primary md:block">
              Explorar leilões
            </Link>
            {user ? (
              <>
                <Link to="/create" className="app-button button-primary">
                  <Icon name="plus" />
                  Anunciar item
                </Link>
                <span className="hidden sm:block">{user.display_name}</span>
                <Button
                  variant="ghost"
                  onClick={async () => {
                    try {
                      await api.logout()
                      await refresh()
                    } catch (e) {
                      setError((e as Error).message)
                    }
                  }}
                >
                  Sair
                </Button>
              </>
            ) : (
              <>
                <Link to="/login" className="app-button button-ghost">
                  Entrar
                </Link>
                <Link to="/register" className="app-button button-primary">
                  Criar conta
                  <Icon name="arrow" className="h-4 w-4" />
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      {error && (
        <div role="alert" className="page-width py-3 text-destructive">
          {error}
        </div>
      )}
      {children}
      <footer className="mt-16 border-t border-border">
        <div className="page-width flex flex-wrap items-center justify-between gap-5 py-8 text-[11px] text-muted-foreground">
          <Link
            to="/"
            className="flex items-center gap-2 font-extrabold text-foreground"
          >
            <Icon name="bolt" className="text-primary" />
            katchau leilões
          </Link>
          <span>
            © {CURRENT_YEAR} Katchau Leilões. Todos os direitos reservados.
          </span>
          <span className="flex items-center gap-2">
            <Icon name="shield" className="h-4 w-4" />
            Transparência em cada lance.
          </span>
        </div>
      </footer>
    </>
  )
}
