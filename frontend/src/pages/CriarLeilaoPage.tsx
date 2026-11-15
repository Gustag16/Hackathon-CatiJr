import {
  useEffect,
  useState,
  type ChangeEvent,
  type FormEvent,
} from 'react'
import { api, ApiError, getServerNowMs } from '../api/api'
import { Link } from '../components/common/Router'
import { Button, Icon } from '../components/common/Ui'
import { toCents, validatePhotos } from '../utils/auctionRules'
import { useAuth } from '../utils/authContext'
import type { ConfigResponse } from '../utils/interfaces/auctionInterface'
import { useNavigate } from '../utils/routerContext'

function defaultStartsAtLocal(): string {
  const d = new Date(Date.now() + 2 * 60 * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const FIELD_LABELS: Record<string, string> = {
  name: 'Título',
  description: 'Descrição',
  category: 'Categoria',
  start_price_cents: 'Lance inicial',
  starts_at: 'Início',
  duration_seconds: 'Duração',
  photos: 'Fotos',
}

function formatDuration(seconds: number): string {
  const units: [number, string, string][] = [
    [86400, 'dia', 'dias'],
    [3600, 'hora', 'horas'],
    [60, 'minuto', 'minutos'],
  ]
  for (const [size, one, many] of units) {
    if (seconds % size === 0) {
      const n = seconds / size
      return `${n} ${n === 1 ? one : many}`
    }
  }
  return `${seconds} segundos`
}

export function CriarLeilaoPage() {
  const { user, loading } = useAuth()
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [error, setError] = useState('')
  const [fields, setFields] = useState<Record<string, string[]>>({})
  const [pending, setPending] = useState(false)
  const [photos, setPhotos] = useState<File[]>([])
  const [urls, setUrls] = useState<string[]>([])
  const navigate = useNavigate()

  useEffect(() => {
    api
      .getConfig()
      .then(setConfig)
      .catch((e) => setError((e as Error).message))
  }, [])

  useEffect(() => {
    return () => {
      urls.forEach((u) => URL.revokeObjectURL(u))
    }
  }, [urls])

  const handlePhotosChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || [])
    setPhotos(selected)
    setUrls(selected.map((f) => URL.createObjectURL(f)))
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setFields({})
    try {
      const limits = config?.limits
      const photoError = validatePhotos(photos, limits)
      if (photoError) throw new Error(photoError)
      const body = new FormData(e.currentTarget)
      const name = String(body.get('name') || '').trim()
      const description = String(body.get('description') || '').trim()
      if (limits && name.length > limits.max_name_length) {
        throw new Error(
          `O título deve ter no máximo ${limits.max_name_length} caracteres.`,
        )
      }
      if (limits && description.length > limits.max_description_length) {
        throw new Error(
          `A descrição deve ter no máximo ${limits.max_description_length} caracteres.`,
        )
      }
      body.set('start_price_cents', String(toCents(String(body.get('price')))))
      body.delete('price')
      const startsAtDate = new Date(String(body.get('starts_at')))
      if (Number.isNaN(startsAtDate.getTime())) {
        throw new Error('Informe uma data de início válida.')
      }
      if (limits) {
        const delaySec = (startsAtDate.getTime() - getServerNowMs()) / 1000
        if (delaySec < limits.min_start_delay_seconds) {
          throw new Error(
            `O início deve ser pelo menos ${limits.min_start_delay_seconds} segundos no futuro.`,
          )
        }
        if (delaySec > limits.max_start_advance_seconds) {
          throw new Error('A data de início excede a antecedência máxima permitida.')
        }
      }
      body.set('starts_at', startsAtDate.toISOString())
      const duration =
        Number(body.get('duration_value')) * Number(body.get('duration_unit'))
      body.delete('duration_value')
      body.delete('duration_unit')
      body.set('duration_seconds', String(duration))
      if (
        !Number.isInteger(duration) ||
        duration < (limits?.min_duration_seconds ?? 60) ||
        (limits?.max_duration_seconds !== undefined &&
          duration > limits.max_duration_seconds)
      ) {
        throw new Error(
          `Informe uma duração entre ${formatDuration(limits?.min_duration_seconds ?? 60)} e ${formatDuration(limits?.max_duration_seconds ?? 604800)}.`,
        )
      }
      body.delete('photos')
      photos.forEach((f) => body.append('photos', f))
      setPending(true)
      const result = await api.createAuction(body)
      await navigate({ to: '/auctions/$id', params: { id: result.id } })
    } catch (e) {
      setError((e as Error).message)
      if (e instanceof ApiError) {
        setFields(e.data.fields || {})
      }
    } finally {
      setPending(false)
    }
  }

  if (loading) {
    return <main className="page-width py-20">Carregando…</main>
  }
  if (!user) {
    return (
      <main className="page-width py-20">
        <h1 className="text-2xl font-extrabold">Anunciar um item</h1>
        <p className="my-4 text-muted-foreground">
          Entre na sua conta para criar um leilão.
        </p>
        <Link to="/login" className="app-button button-primary">
          Entrar
          <Icon name="arrow" />
        </Link>
      </main>
    )
  }

  return (
    <main className="page-width py-10">
      <Link to="/" className="text-xs text-muted-foreground">
        ← Voltar aos leilões
      </Link>
      <h1 className="mb-2 mt-6 text-3xl font-extrabold">Anunciar um item</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        Um novo item. Uma nova disputa.
      </p>
      <form onSubmit={submit} className="max-w-3xl space-y-6">
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <label className="block">
          <span className="field-label">Título do item</span>
          <input
            className="field"
            name="name"
            required
            maxLength={config?.limits.max_name_length ?? 100}
          />
        </label>
        <label className="block">
          <span className="field-label">Descrição</span>
          <textarea
            className="field min-h-32"
            name="description"
            required
            maxLength={config?.limits.max_description_length ?? 2000}
          />
        </label>
        <div className="grid gap-5 sm:grid-cols-2">
          <label>
            <span className="field-label">Categoria</span>
            <select className="field" name="category" required>
              <option value="">Selecione</option>
              {config?.categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="field-label">Lance inicial (R$)</span>
            <input
              className="field"
              name="price"
              inputMode="decimal"
              placeholder="0,00"
              required
            />
          </label>
          <label>
            <span className="field-label">Data e horário de início</span>
            <input
              className="field"
              name="starts_at"
              type="datetime-local"
              defaultValue={defaultStartsAtLocal()}
              required
            />
          </label>
          <div>
            <label className="field-label" htmlFor="duration-value">
              Duração
            </label>
            <div className="flex gap-2">
              <input
                id="duration-value"
                className="field min-w-0"
                type="number"
                name="duration_value"
                min="1"
                step="1"
                defaultValue={24}
                required
              />
              <select
                className="field"
                name="duration_unit"
                aria-label="Unidade da duração"
                defaultValue="3600"
              >
                <option value="60">minutos</option>
                <option value="3600">horas</option>
                <option value="86400">dias</option>
              </select>
            </div>
            <span className="mt-1 block text-xs text-muted-foreground">
              De {formatDuration(config?.limits.min_duration_seconds ?? 60)} a{' '}
              {formatDuration(config?.limits.max_duration_seconds ?? 604800)}.
            </span>
          </div>
        </div>
        <label className="block">
          <span className="field-label">
            Fotos do item · {config?.limits.min_photos ?? 3} a{' '}
            {config?.limits.max_photos ?? 8} imagens
          </span>
          <input
            className="field"
            type="file"
            name="photos"
            multiple
            accept="image/jpeg,image/png,image/webp"
            onChange={handlePhotosChange}
          />
          <span className="mt-2 block text-xs text-muted-foreground">
            JPEG, PNG ou WebP. Até{' '}
            {Math.round((config?.limits.max_photo_bytes ?? 5242880) / 1048576)}{' '}
            MB por foto.
            {photos.length > 0 &&
              ` ${photos.length} ${photos.length === 1 ? 'foto selecionada' : 'fotos selecionadas'}.`}
          </span>
        </label>
        {urls.length > 0 && (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
            {urls.map((url, i) => (
              <img
                key={url}
                src={url}
                alt={`Foto ${i + 1}`}
                className="aspect-square rounded object-cover"
              />
            ))}
          </div>
        )}
        {Object.entries(fields).map(([field, messages]) => (
          <p key={field} role="alert" className="text-sm text-destructive">
            {FIELD_LABELS[field] ?? field}: {messages.join(' ')}
          </p>
        ))}
        <Button disabled={pending || !config}>
          <Icon name="plus" />
          {pending ? 'Publicando…' : 'Publicar leilão'}
        </Button>
      </form>
    </main>
  )
}
