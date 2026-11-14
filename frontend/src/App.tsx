import { useEffect } from 'react'
import { AuthProvider } from './components/common/AuthProvider'
import { Link, RouterProvider } from './components/common/Router'
import { Shell } from './components/common/Shell'
import { CriarLeilaoPage } from './pages/CriarLeilaoPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { SalaLeilaoPage } from './pages/SalaLeilaoPage'
import { useLocation } from './utils/routerContext'

function Routes() {
  const { pathname, search } = useLocation()

  useEffect(() => {
    if (pathname === '/') {
      document.title = 'Katchau Leilões | O próximo grande achado é seu'
    } else if (pathname === '/login') {
      document.title = 'Entrar | Katchau Leilões'
    } else if (pathname === '/register') {
      document.title = 'Criar conta | Katchau Leilões'
    } else if (pathname === '/create') {
      document.title = 'Anunciar item | Katchau Leilões'
    } else if (pathname.startsWith('/auctions/')) {
      document.title = 'Sala do Leilão | Katchau Leilões'
    } else {
      document.title = 'Katchau Leilões'
    }
  }, [pathname])

  if (pathname === '/' || pathname === '') {
    return <HomePage />
  }

  if (pathname === '/login') {
    const params = new URLSearchParams(search)
    const registered = params.get('registered') === 'true'
    return <LoginPage registered={registered} />
  }

  if (pathname === '/register') {
    return <RegisterPage />
  }

  if (pathname === '/create') {
    return <CriarLeilaoPage />
  }

  const auctionMatch = /^\/auctions\/([^/]+)\/?$/.exec(pathname)
  if (auctionMatch) {
    const auctionId = decodeURIComponent(auctionMatch[1])
    return <SalaLeilaoPage key={auctionId} id={auctionId} />
  }

  return (
    <main className="page-width py-20 text-center">
      <h1 className="text-6xl font-extrabold text-foreground">404</h1>
      <h2 className="mt-4 text-xl font-bold text-foreground">
        Página não encontrada
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">
        A página que você procura não existe ou foi movida.
      </p>
      <div className="mt-6">
        <Link to="/" className="app-button button-primary">
          Voltar ao início
        </Link>
      </div>
    </main>
  )
}

export default function App() {
  return (
    <RouterProvider>
      <AuthProvider>
        <Shell>
          <Routes />
        </Shell>
      </AuthProvider>
    </RouterProvider>
  )
}
