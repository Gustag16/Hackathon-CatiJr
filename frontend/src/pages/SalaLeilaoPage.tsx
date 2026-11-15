import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/api'
import { connectAuctionRoomWs } from '../api/ws'
import { Link } from '../components/common/Router'
import { Button, Icon, Notice, StatusBadge } from '../components/common/Ui'
import { Cronometro } from '../components/salaLeilao/Cronometro'
import { FormularioLance } from '../components/salaLeilao/FormularioLance'
import { HistoricoLances } from '../components/salaLeilao/HistoricoLances'
import { ModalCancelar } from '../components/salaLeilao/ModalCancelar'
import {
  bidsLabel,
  canCancel,
  categoryLabel,
  definitiveBidResponse,
  formatLeaderText,
  generateUUID,
  money,
  toCents,
} from '../utils/auctionRules'
import { useAuth } from '../utils/authContext'
import type { Auction } from '../utils/interfaces/auctionInterface'
import type { Bid, PendingBidState } from '../utils/interfaces/bidInterface'

function loadPendingBid(auctionId: string): PendingBidState | null {
  try {
    const raw = sessionStorage.getItem(`katchau_pending_bid_${auctionId}`)
    if (!raw) return null
    const parsed = JSON.parse(raw) as PendingBidState
    if (
      typeof parsed?.key === 'string' &&
      Number.isSafeInteger(parsed?.amount_cents)
    ) {
      return parsed
    }
  } catch {
    // ignore
  }
  return null
}

function savePendingBid(auctionId: string, state: PendingBidState | null) {
  try {
    const storageKey = `katchau_pending_bid_${auctionId}`
    if (!state) {
      sessionStorage.removeItem(storageKey)
    } else {
      sessionStorage.setItem(storageKey, JSON.stringify(state))
    }
  } catch {
    // ignore
  }
}

export function SalaLeilaoPage({ id }: { id: string }) {
  const { user } = useAuth()
  const [auction, setAuction] = useState<Auction | null>(null)
  const [photo, setPhoto] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [connected, setConnected] = useState(false)
  const [everConnected, setEverConnected] = useState(false)
  const [participant, setParticipant] = useState<number | null>(null)
  const participantRef = useRef<number | null>(null)
  const [bids, setBids] = useState<Bid[]>([])
  const [pending, setPending] = useState(false)
  const [amount, setAmount] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [rateLimited, setRateLimited] = useState(false)
  const rateLimitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingBid = useRef<PendingBidState | null>(loadPendingBid(id))
  const [pendingBidState, setPendingBidState] =
    useState<PendingBidState | null>(() => loadPendingBid(id))

  const updatePendingBid = (next: PendingBidState | null) => {
    pendingBid.current = next
    setPendingBidState(next)
    savePendingBid(id, next)
  }

  useEffect(() => {
    return () => {
      if (rateLimitTimerRef.current) {
        clearTimeout(rateLimitTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    let active = true
    api
      .getAuction(id)
      .then((a) => {
        if (active) {
          setAuction(a)
          setPhoto(a.cover_photo_url)
        }
      })
      .catch((e) => {
        if (active) setError((e as Error).message)
      })
    return () => {
      active = false
    }
  }, [id])

  const userId = user?.id ?? null
  const hasAuction = Boolean(auction)

  useEffect(() => {
    if (!userId || !hasAuction) return

    return connectAuctionRoomWs(id, {
      onConnectionChange: (value) => {
        setConnected(value)
        if (value) setEverConnected(true)
      },
      onEvent: (event) => {
        if (event.type === 'snapshot') {
          participantRef.current = event.you?.participant_number ?? null
          setParticipant(participantRef.current)
          setBids(event.recent_bids || [])
          setAuction((a) =>
            a ? { ...a, ...event.auction, result: event.result ?? null } : a,
          )
        } else if (event.type === 'bid_accepted') {
          setAuction((a) => (a ? { ...a, ...event.auction } : a))
          if (event.bid) {
            const accepted = event.bid
            setBids((b) =>
              [accepted, ...b.filter((v) => v.id !== accepted.id)].slice(0, 20),
            )
          }
          if (
            event.previous_leader_number !== null &&
            event.previous_leader_number !== undefined &&
            event.previous_leader_number === participantRef.current
          ) {
            setNotice('Seu lance foi superado!')
          }
          if (event.extended) {
            setNotice(
              (n) => `${n ? n + ' ' : ''}Leilão prorrogado por mais 2 minutos.`,
            )
          }
        } else if (
          ['auction_started', 'auction_finished', 'auction_cancelled'].includes(
            event.type,
          )
        ) {
          setAuction((a) =>
            a
              ? {
                  ...a,
                  ...event.auction,
                  ...(event.type === 'auction_finished'
                    ? { result: event.result ?? null }
                    : {}),
                }
              : a,
          )
          if (event.type === 'auction_finished') {
            setNotice('Leilão encerrado. Confira o resultado.')
          }
          if (event.type === 'auction_cancelled') {
            setNotice('O leilão foi cancelado.')
          }
        }
      },
    })
  }, [id, userId, hasAuction])

  async function bid(custom: boolean, retry = false) {
    if (!auction || !connected) return
    setError('')
    try {
      const value = retry
        ? pendingBid.current?.amount_cents
        : custom
          ? toCents(amount)
          : auction.min_next_bid_cents
      if (value === undefined || !Number.isSafeInteger(value)) {
        throw new Error('Aguarde a atualização do lance mínimo.')
      }

      if (
        !pendingBid.current ||
        (!retry && pendingBid.current.amount_cents !== value)
      ) {
        updatePendingBid({
          key: generateUUID(),
          amount_cents: value,
        })
      }

      setPending(true)
      const prepared = pendingBid.current!
      const res = await api.placeBid(id, prepared.amount_cents, prepared.key)
      updatePendingBid(null)
      if (res?.you?.participant_number !== undefined) {
        participantRef.current = res.you.participant_number
        setParticipant(res.you.participant_number)
      }
      if (res?.auction) {
        setAuction((a) => (a ? { ...a, ...res.auction } : a))
      }
      if (custom) {
        setAmount('')
      }
      setNotice('Lance enviado com sucesso.')
    } catch (e) {
      let msg = (e as Error).message
      if (e instanceof ApiError) {
        if (definitiveBidResponse(e.status)) {
          updatePendingBid(null)
        }
        if (e.data.auction) {
          setAuction((a) => (a ? { ...a, ...e.data.auction } : a))
        }
        const minimum =
          e.data.min_bid_cents ?? e.data.auction?.min_next_bid_cents
        if (minimum !== undefined) {
          setAuction((a) => (a ? { ...a, min_next_bid_cents: minimum } : a))
          if (e.status === 409 && !msg.includes('R$')) {
            msg = `${msg} (Lance mínimo atual: ${money(minimum)})`
          }
        }
        if (e.status === 429) {
          setRateLimited(true)
          if (rateLimitTimerRef.current) {
            clearTimeout(rateLimitTimerRef.current)
          }
          rateLimitTimerRef.current = setTimeout(() => {
            setRateLimited(false)
          }, e.data.retry_after_ms || 5000)
        }
      }
      setError(msg)
    } finally {
      setPending(false)
    }
  }

  async function cancel() {
    setPending(true)
    setError('')
    try {
      await api.cancelAuction(id)
      setAuction((a) => (a ? { ...a, status: 'cancelled' } : a))
      setConfirm(false)
      setNotice('Leilão cancelado.')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPending(false)
    }
  }

  if (!auction) {
    return (
      <main className="page-width py-20">
        {error ? (
          <>
            <p role="alert" className="mb-4 text-destructive">
              {error}
            </p>
            <Link to="/">← Voltar aos leilões</Link>
          </>
        ) : (
          'Carregando leilão…'
        )}
      </main>
    )
  }

  const lead =
    participant !== null &&
    auction.leader_number !== null &&
    auction.leader_number !== undefined &&
    auction.leader_number === participant
  const disabled =
    !connected ||
    pending ||
    auction.status !== 'running' ||
    auction.min_next_bid_cents === undefined ||
    rateLimited
  const finished = ['sold', 'ended_no_bids', 'cancelled'].includes(
    auction.status,
  )
  const isSeller = user?.id === auction.seller.id
  const photos = auction.photos || []
  const endedAt = new Date(auction.ends_at).toLocaleString('pt-BR')
  const outcome =
    auction.status === 'sold'
      ? `Arrematado por ${
          auction.result?.winner_label ?? auction.leader_label ?? 'um participante'
        } por ${money(
          auction.result?.final_price_cents ?? auction.current_price_cents,
        )}.`
      : auction.status === 'ended_no_bids'
        ? 'Leilão encerrado sem lances.'
        : auction.status === 'cancelled'
          ? 'Este leilão foi cancelado pelo comitente.'
          : ''

  return (
    <main className="page-width py-8">
      <Link to="/" className="text-xs text-muted-foreground">
        ← Explorar leilões
      </Link>
      <div className="mb-6 mt-7 flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="text-xs text-muted-foreground">
            {categoryLabel(auction.category)}
          </span>
          <h1 className="mt-2 break-words text-3xl font-extrabold">
            {auction.name}
          </h1>
          <p className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
            <Icon name="user" className="h-4 w-4" />
            {auction.seller.display_name}
          </p>
        </div>
        <StatusBadge status={auction.status} />
      </div>

      {/* No celular a ordem é foto, painel de lance, descrição; no desktop o painel fica à direita. */}
      <div className="grid items-start gap-8 lg:grid-cols-[1.4fr_1fr] lg:grid-rows-[auto_1fr]">
        <section>
          <img
            src={photo}
            alt={auction.name}
            width={1024}
            height={768}
            className="aspect-[4/3] w-full rounded-lg bg-muted object-cover"
          />
          {photos.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-3">
              {photos.map((p, index) => (
                <button
                  key={p.id}
                  type="button"
                  aria-label={`Ver foto ${index + 1} de ${photos.length}`}
                  aria-pressed={photo === p.url}
                  onClick={() => setPhoto(p.url)}
                  className="photo-thumb"
                >
                  <img
                    src={p.url}
                    alt=""
                    loading="lazy"
                    className="h-16 w-20 object-cover"
                  />
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="lg:col-start-2 lg:row-span-2 lg:row-start-1">
          <div className="rounded-lg border border-border bg-card p-6">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>
                {finished
                  ? 'Leilão encerrado'
                  : auction.status === 'scheduled'
                    ? 'Começa em'
                    : 'Tempo restante'}
              </span>
              <span>{bidsLabel(auction.bid_count)}</span>
            </div>
            <div className="mt-3">
              {finished ? (
                <p className="py-2 text-sm font-semibold text-muted-foreground">
                  {auction.status === 'cancelled'
                    ? 'Cancelado antes do término.'
                    : `Encerrado em ${endedAt}`}
                </p>
              ) : (
                <Cronometro
                  end={
                    auction.status === 'scheduled'
                      ? auction.starts_at
                      : auction.ends_at
                  }
                  status={auction.status}
                  large
                />
              )}
            </div>
            <div className="my-5 border-t border-border pt-5">
              <p className="text-xs text-muted-foreground">
                {auction.status === 'sold'
                  ? 'Valor final'
                  : auction.bid_count === 0
                    ? 'Lance inicial'
                    : 'Lance atual'}
              </p>
              <p className="mt-2 text-4xl font-extrabold tabular-nums">
                {money(auction.current_price_cents)}
              </p>
            </div>
            {outcome && (
              <div className="mb-4">
                <Notice>{outcome}</Notice>
              </div>
            )}
            {user && !finished && (
              <>
                {auction.status === 'running' && (
                  <p
                    className={`mb-4 text-xs font-bold ${
                      lead ? 'text-success' : 'text-muted-foreground'
                    }`}
                  >
                    {lead
                      ? `Você lidera! (#${participant})`
                      : formatLeaderText(auction)}
                  </p>
                )}
                {!connected && (
                  <p
                    role="status"
                    className={`mb-4 text-xs ${
                      everConnected
                        ? 'text-destructive'
                        : 'text-muted-foreground'
                    }`}
                  >
                    {everConnected
                      ? 'Reconectando… os lances ficam desabilitados até a conexão voltar.'
                      : 'Conectando à sala…'}
                  </p>
                )}
              </>
            )}
            {notice && (
              <div className="mb-4">
                <Notice>{notice}</Notice>
              </div>
            )}
            {error && (
              <p role="alert" className="mb-4 text-sm text-destructive">
                {error}
              </p>
            )}

            {finished ? (
              <Link to="/" className="app-button button-outline w-full">
                Ver outros leilões
                <Icon name="arrow" className="h-4 w-4" />
              </Link>
            ) : isSeller ? (
              <p className="rounded-md bg-muted p-3 text-xs leading-relaxed text-muted-foreground">
                Você é o comitente deste leilão: acompanha a disputa em tempo
                real, mas não pode dar lances.
              </p>
            ) : user && auction.status === 'scheduled' ? (
              <p className="rounded-md bg-muted p-3 text-xs leading-relaxed text-muted-foreground">
                Os lances abrem quando o leilão começar. Lance inicial:{' '}
                {money(auction.current_price_cents)}.
              </p>
            ) : (
              <FormularioLance
                loggedIn={Boolean(user)}
                disabled={disabled}
                pending={pending}
                minNextBidCents={auction.min_next_bid_cents || 0}
                amount={amount}
                onAmountChange={setAmount}
                onQuickBid={() => bid(false)}
                onCustomBid={() => bid(true)}
                pendingBidState={pendingBidState}
                onRetryPendingBid={() => bid(false, true)}
              />
            )}

            {auction.status === 'running' && (
              <p className="mt-5 text-[11px] leading-relaxed text-muted-foreground">
                Lances nos 2 minutos finais prorrogam o leilão em mais 2
                minutos.
              </p>
            )}
          </div>

          {canCancel(auction, user) && (
            <div className="mt-4">
              <Button variant="outline" onClick={() => setConfirm(true)}>
                Cancelar leilão
              </Button>
            </div>
          )}

          <HistoricoLances loggedIn={Boolean(user)} bids={bids} />
        </section>

        <section>
          <h2 className="mb-3 text-lg font-extrabold">Sobre o item</h2>
          <p className="whitespace-pre-line break-words text-sm leading-7 text-muted-foreground">
            {auction.description}
          </p>
          <div className="mt-7 border-t border-border pt-5 text-xs text-muted-foreground">
            Início: {new Date(auction.starts_at).toLocaleString('pt-BR')}
            <br />
            {finished ? 'Encerrado' : 'Encerramento previsto'}: {endedAt}
          </div>
        </section>
      </div>

      <ModalCancelar
        open={confirm}
        pending={pending}
        onClose={() => setConfirm(false)}
        onConfirm={cancel}
      />
    </main>
  )
}
