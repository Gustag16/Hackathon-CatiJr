import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../api/api'
import { Link } from '../components/common/Router'
import { Button, Icon, Notice } from '../components/common/Ui'
import { useAuth } from '../utils/authContext'
import { useNavigate } from '../utils/routerContext'

export function LoginPage({ registered = false }: { registered?: boolean }) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [fields, setFields] = useState<Record<string, string[]>>({})
  const { refresh } = useAuth()
  const navigate = useNavigate()

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setPending(true)
    setError('')
    setFields({})
    const form = new FormData(e.currentTarget)
    try {
      await api.login({
        email: String(form.get('email')).trim(),
        password: String(form.get('password')),
      })
      await refresh()
      await navigate({ to: '/' })
    } catch (e) {
      setError((e as Error).message)
      if (e instanceof ApiError) {
        setFields(e.data.fields || {})
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="page-width">
      <section className="form-panel">
        <span className="mb-6 flex h-12 w-12 items-center justify-center rounded-lg bg-warning-soft text-primary">
          <Icon name="bolt" className="h-7 w-7" />
        </span>
        <h1 className="text-2xl font-extrabold">Bom ter você de volta.</h1>
        <p className="mb-7 mt-3 text-sm text-muted-foreground">
          Entre na sua conta e participe da disputa.
        </p>
        {registered && (
          <div className="mb-5">
            <Notice>Conta criada com sucesso! Entre para continuar.</Notice>
          </div>
        )}
        {error && (
          <p role="alert" className="mb-4 text-sm text-destructive">
            {error}
          </p>
        )}
        <form onSubmit={submit} className="space-y-5">
          <label className="block">
            <span className="field-label">E-mail</span>
            <input
              className="field"
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="voce@exemplo.com"
            />
            {fields['email']?.map((message) => (
              <span
                className="mt-1 block text-xs text-destructive"
                key={message}
              >
                {message}
              </span>
            ))}
          </label>
          <label className="block">
            <span className="field-label">Senha</span>
            <input
              className="field"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              placeholder="Sua senha"
            />
            {fields['password']?.map((message) => (
              <span
                className="mt-1 block text-xs text-destructive"
                key={message}
              >
                {message}
              </span>
            ))}
          </label>
          <Button className="w-full" disabled={pending}>
            {pending ? 'Aguarde…' : 'Entrar'}
            <Icon name="arrow" className="h-4 w-4" />
          </Button>
        </form>
        <p className="mt-6 text-center text-xs text-muted-foreground">
          Ainda não tem uma conta?{' '}
          <Link to="/register" className="font-bold text-foreground">
            Criar conta
          </Link>
        </p>
      </section>
    </main>
  )
}
