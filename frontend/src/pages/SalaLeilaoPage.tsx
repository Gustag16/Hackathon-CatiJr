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
import { sampleAuctions } from '../utils/samples'

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
  const [demo, setDemo] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [connected, setConnected] = useState(false)
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
          setDemo(false)
        }
      })
      .catch((e) => {
        if (!active) return
        const sample = sampleAuctions().find((a) => a.id === id)
        if (sample) {
          setAuction(sample)
          setPhoto(sample.cover_photo_url)
          setDemo(true)
        } else {
          setError((e as Error).message)
        }
      })
    return () => {
      active = false
    }
  }, [id])

  const userId = user?.id ?? null
  const hasAuction = Boolean(auction)

  useEffect(() => {
    if (!userId || demo || !hasAuction) return

    return connectAuctionRoomWs(id, {
      onConnectionChange: setConnected,
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
  }, [id, userId, demo, hasAuction])

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
      if (e instanceof ApiError) {
        if (definitiveBidResponse(e.status)) {
          updatePendingBid(null)
        }
        if (e.data.auction) {
          setAuction((a) => (a ? { ...a, ...e.data.auction } : a))
        }
        if (e.data.min_bid_cents !== undefined) {
          const minimum = e.data.min_bid_cents
          setAuction((a) => (a ? { ...a, min_next_bid_cents: minimum } : a))
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
      setError((e as Error).message)
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

  return (
    <main className="page-width py-8">
      <Link to="/" className="text-xs text-muted-foreground">
        ← Explorar leilões
      </Link>
      {demo && (
        <div className="mt-5">
          <Notice>
            Item ilustrativo · A API Django ainda não está conectada. Não é
            possível enviar lances nesta prévia.
          </Notice>
        </div>
      )}
      <div className="mb-6 mt-7 flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="text-xs text-muted-foreground">
            {categoryLabel(auction.category)}
          </span>
          <h1 className="mt-2 text-3xl font-extrabold">{auction.name}</h1>
          <p className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
            <Icon name="user" className="h-4 w-4" />
            {auction.seller.display_name}
          </p>
        </div>
        <StatusBadge status={auction.status} />
      </div>

      <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <section>
          <img
            src={photo}
            alt={auction.name}
            width={1024}
            height={768}
            className="aspect-[4/3] w-full rounded-lg bg-muted object-cover"
          />
          <div className="mt-3 flex flex-wrap gap-3">
            {(auction.photos || []).map((p) => (
              <Button
                key={p.id}
                variant="outline"
                aria-label={`Ver foto ${p.id}`}
                onClick={() => setPhoto(p.url)}
                className={`overflow-hidden p-0 ${
                  photo === p.url ? 'ring-2 ring-primary' : ''
                }`}
              >
                <img
                  src={p.url}
                  alt={`Miniatura ${p.id}`}
                  className="h-16 w-20 object-cover"
                />
              </Button>
            ))}
          </div>
          <h2 className="mb-3 mt-8 text-lg font-extrabold">Sobre o item</h2>
          <p className="whitespace-pre-line text-sm leading-7 text-muted-foreground">
            {auction.description}
          </p>
          <div className="mt-7 border-t border-border pt-5 text-xs text-muted-foreground">
            Início: {new Date(auction.starts_at).toLocaleString('pt-BR')}
            <br />
            Encerramento: {new Date(auction.ends_at).toLocaleString('pt-BR')}
          </div>
        </section>

        <section>
          <div className="rounded-lg border border-border bg-card p-6">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>
                {auction.status === 'scheduled'
                  ? 'Começa em'
                  : 'Tempo restante'}
              </span>
              <span>{auction.bid_count} lances</span>
            </div>
            <div className="mt-3">
              <Cronometro
                end={
                  auction.status === 'scheduled'
                    ? auction.starts_at
                    : auction.ends_at
                }
                status={auction.status}
                large
              />
            </div>
            <div className="my-5 border-t border-border pt-5">
              <p className="text-xs text-muted-foreground">
                {auction.bid_count === 0 ? 'Lance inicial' : 'Lance atual'}
              </p>
              <p className="mt-2 text-4xl font-extrabold">
                {money(auction.current_price_cents)}
              </p>
            </div>
            {auction.result && (
              <div className="mb-4">
                <Notice>
                  {auction.result.status === 'sold'
                    ? `Arrematado por ${auction.result.winner_label} por ${money(
                        auction.result.final_price_cents || 0,
                      )}.`
                    : 'Leilão encerrado sem arremate.'}
                </Notice>
              </div>
            )}
            {user && !demo && (
              <>
                <p
                  className={`mb-4 text-xs font-bold ${
                    lead ? 'text-success' : 'text-muted-foreground'
                  }`}
                >
                  {lead
                    ? `Você lidera! (#${participant})`
                    : formatLeaderText(auction)}
                </p>
                {!connected && (
                  <p role="status" className="mb-4 text-xs text-destructive">
                    Reconectando...
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

            <FormularioLance
              loggedIn={Boolean(user && !demo)}
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

            <p className="mt-5 text-[11px] leading-relaxed text-muted-foreground">
              Lances nos 2 minutos finais prorrogam o leilão em mais 2 minutos.
            </p>
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
