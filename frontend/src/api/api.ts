import type {
  ApiErrorPayload,
  Auction,
  AuctionPage,
  BidAcceptedResponse,
  ConfigResponse,
  HealthResponse,
} from '../utils/interfaces/auctionInterface'
import type { User } from '../utils/interfaces/userInterface'

// ============================================================================
// 1. Sincronia de relógio com o servidor (RF16 / Contrato Seção 1)
// offset = server_time - Date.now()
// ============================================================================
let serverTimeOffsetMs = 0

export function updateServerTime(serverTimeIso?: string | null): void {
  if (!serverTimeIso) return
  const parsed = new Date(serverTimeIso).getTime()
  if (!Number.isNaN(parsed)) {
    serverTimeOffsetMs = parsed - Date.now()
  }
}

export function getServerNowMs(): number {
  return Date.now() + serverTimeOffsetMs
}

export function getServerTimeOffsetMs(): number {
  return serverTimeOffsetMs
}

export const getOffset = getServerTimeOffsetMs
export const syncClock = updateServerTime

// ============================================================================
// 2. Utilitário de dinheiro em centavos (RF19 / D1)
// ============================================================================
const brlFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

export function formatCentsToBRL(cents: number): string {
  return brlFormatter.format(cents / 100)
}

// ============================================================================
// 3. Leitura e garantia do cookie CSRF (D2 / Contrato Seção 1 e 3)
// Lê document.cookie a CADA requisição (nunca guarda em variável fixa, pois
// o Django rotaciona o csrftoken após o login).
// ============================================================================
export function getCsrfCookie(): string | null {
  const cookies = document.cookie ? document.cookie.split(';') : []
  for (const rawCookie of cookies) {
    const cookie = rawCookie.trim()
    if (cookie.startsWith('csrftoken=')) {
      return decodeURIComponent(cookie.slice('csrftoken='.length))
    }
  }
  return null
}

let csrfPromise: Promise<void> | null = null

export async function ensureCsrf(forceRefresh = false): Promise<string | null> {
  if (!forceRefresh) {
    const existing = getCsrfCookie()
    if (existing) return existing
  }

  if (!csrfPromise) {
    csrfPromise = fetch('/api/auth/csrf', {
      method: 'GET',
      credentials: 'same-origin',
    })
      .then(() => {
        csrfPromise = null
      })
      .catch((err) => {
        csrfPromise = null
        throw err
      })
  }

  await csrfPromise
  return getCsrfCookie()
}

// ============================================================================
// 4. Classe única de erro da API ({ code, message, ...extras })
// ============================================================================
export class ApiError extends Error {
  status: number
  code: string
  data: ApiErrorPayload
  fields?: Record<string, string[]>
  reason?: string
  min_bid_cents?: number
  retry_after_ms?: number
  auction?: ApiErrorPayload['auction']

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message || 'Erro na comunicação com o servidor.')
    this.name = 'ApiError'
    this.status = status
    this.code = payload.code || 'UNKNOWN_ERROR'
    this.data = payload
    this.fields = payload.fields
    this.reason = payload.reason
    this.min_bid_cents = payload.min_bid_cents
    this.retry_after_ms = payload.retry_after_ms
    this.auction = payload.auction
  }

  /**
   * RF12: Respostas não definitivas em lances (401, 429, 5xx ou falha de rede)
   * devem reutilizar a MESMA Idempotency-Key ao tentar novamente.
   */
  isNonDefinitiveBidError(): boolean {
    return (
      this.status === 401 ||
      this.status === 429 ||
      this.status >= 500 ||
      this.status === 0
    )
  }

  /**
   * Retorna a primeira mensagem de erro de um campo específico em 400 VALIDATION_ERROR
   */
  getFieldError(field: string): string | null {
    const list = this.fields?.[field]
    return list && list.length > 0 ? list[0] : null
  }
}

type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null

export function setOnUnauthorized(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

// ============================================================================
// 5. Função central de requisição (todas as chamadas passam por aqui)
// ============================================================================
export interface ApiRequestOptions {
  method?: string
  body?: unknown
  headers?: HeadersInit
  notifyUnauthorized?: boolean
}

const MUTATING_METHODS = new Set(['POST', 'PATCH', 'DELETE'])

export async function apiFetch<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers = new Headers(options.headers)
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }

  if (MUTATING_METHODS.has(method)) {
    const token = (await ensureCsrf()) ?? getCsrfCookie()
    if (token) {
      headers.set('X-CSRFToken', token)
    }
  }

  let requestBody: BodyInit | undefined
  if (options.body instanceof FormData) {
    requestBody = options.body
  } else if (typeof options.body === 'string') {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    requestBody = options.body
  } else if (options.body !== undefined && options.body !== null) {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    requestBody = JSON.stringify(options.body)
  }

  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers,
      body: requestBody,
      credentials: 'same-origin',
    })
  } catch {
    throw new ApiError(0, {
      code: 'NETWORK_ERROR',
      message: 'Falha de conexão com o servidor. Verifique sua rede.',
    })
  }

  if (response.status === 204) {
    return undefined as T
  }

  let data: unknown = null
  try {
    data = await response.json()
  } catch {
    data = null
  }

  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>
    if (typeof obj.server_time === 'string') {
      updateServerTime(obj.server_time)
    } else if (
      obj.auction &&
      typeof obj.auction === 'object' &&
      typeof (obj.auction as Record<string, unknown>).server_time === 'string'
    ) {
      updateServerTime(
        (obj.auction as Record<string, unknown>).server_time as string,
      )
    }
  }

  if (!response.ok) {
    const payload: ApiErrorPayload =
      data && typeof data === 'object' && 'message' in data
        ? (data as ApiErrorPayload)
        : {
            code: `HTTP_${response.status}`,
            message: 'O serviço de leilões está indisponível. Tente novamente.',
          }

    if (
      response.status === 401 &&
      payload.code === 'NOT_AUTHENTICATED' &&
      options.notifyUnauthorized !== false &&
      unauthorizedHandler
    ) {
      unauthorizedHandler()
    }

    throw new ApiError(response.status, payload)
  }

  if (data === null) {
    throw new ApiError(503, {
      code: 'NOT_CONNECTED',
      message: 'A API de leilões ainda não está conectada.',
    })
  }

  return data as T
}

// ============================================================================
// 6. Endpoints prontos do Contrato v1.3 (Seções 3 e 4)
// ============================================================================
export const api = Object.assign(apiFetch, {
  getHealth(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>('/api/health')
  },

  getConfig(): Promise<ConfigResponse> {
    return apiFetch<ConfigResponse>('/api/config')
  },

  ensureCsrf,

  register(input: {
    display_name: string
    email: string
    password: string
  }): Promise<User> {
    return apiFetch<User>('/api/auth/register', {
      method: 'POST',
      body: input,
    })
  },

  login(input: {
    email: string
    password: string
  }): Promise<{ user: User }> {
    return apiFetch<{ user: User }>('/api/auth/login', {
      method: 'POST',
      body: input,
    })
  },

  logout(): Promise<void> {
    return apiFetch<void>('/api/auth/logout', {
      method: 'POST',
    })
  },

  getMe(): Promise<User> {
    return apiFetch<User>('/api/auth/me', {
      method: 'GET',
      notifyUnauthorized: false,
    })
  },

  listAuctions(params?: {
    status?: 'running' | 'scheduled' | 'running,scheduled'
    page?: number
    page_size?: number
  }): Promise<AuctionPage> {
    const search = new URLSearchParams()
    search.set('status', params?.status ?? 'running,scheduled')
    search.set('page', String(params?.page ?? 1))
    search.set('page_size', String(params?.page_size ?? 12))
    return apiFetch<AuctionPage>(`/api/auctions?${search.toString()}`)
  },

  getAuction(id: string): Promise<Auction> {
    return apiFetch<Auction>(`/api/auctions/${encodeURIComponent(id)}`)
  },

  createAuction(formData: FormData): Promise<Auction> {
    return apiFetch<Auction>('/api/auctions', {
      method: 'POST',
      body: formData,
    })
  },

  cancelAuction(id: string): Promise<Auction> {
    return apiFetch<Auction>(
      `/api/auctions/${encodeURIComponent(id)}/cancel`,
      {
        method: 'POST',
      },
    )
  },

  placeBid(
    auctionId: string,
    amountCents: number,
    idempotencyKey: string,
  ): Promise<BidAcceptedResponse> {
    return apiFetch<BidAcceptedResponse>(
      `/api/auctions/${encodeURIComponent(auctionId)}/bids`,
      {
        method: 'POST',
        headers: {
          'Idempotency-Key': idempotencyKey,
        },
        body: { amount_cents: amountCents },
      },
    )
  },
})
