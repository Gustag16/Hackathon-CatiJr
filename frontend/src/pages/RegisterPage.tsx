import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../api/api'
import { Link } from '../components/common/Router'
import { Button, Icon } from '../components/common/Ui'
import { useNavigate } from '../utils/routerContext'

export function RegisterPage() {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [fields, setFields] = useState<Record<string, string[]>>({})
  const navigate = useNavigate()

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setPending(true)
    setError('')
    setFields({})
    const form = new FormData(e.currentTarget)
    try {
      await api.register({
        display_name: String(form.get('display_name')).trim(),
        email: String(form.get('email')).trim(),
        password: String(form.get('password')),
      })
      await navigate({ to: '/login', search: { registered: true } })
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
          <Icon name="user" className="h-7 w-7" />
        </span>
        <h1 className="text-2xl font-extrabold">
          Sua próxima conquista começa aqui.
        </h1>
        <p className="mb-7 mt-3 text-sm text-muted-foreground">
          Crie sua conta no Katchau Leilões.
        </p>
        {error && (
          <p role="alert" className="mb-4 text-sm text-destructive">
            {error}
          </p>
        )}
        <form onSubmit={submit} className="space-y-5">
          <label className="block">
            <span className="field-label">Nome de exibição</span>
            <input
              className="field"
              name="display_name"
              type="text"
              required
              maxLength={60}
              autoComplete="nickname"
              placeholder="Como podemos chamar você?"
            />
            {fields['display_name']?.map((message) => (
              <span
                className="mt-1 block text-xs text-destructive"
                key={message}
              >
                {message}
              </span>
            ))}
          </label>
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
              autoComplete="new-password"
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
            {pending ? 'Aguarde…' : 'Criar minha conta'}
            <Icon name="arrow" className="h-4 w-4" />
          </Button>
        </form>
        <p className="mt-6 text-center text-xs text-muted-foreground">
          Já tem uma conta?{' '}
          <Link to="/login" className="font-bold text-foreground">
            Entrar
          </Link>
        </p>
      </section>
    </main>
  )
}
