import { retryDelay } from '../utils/auctionRules'
import type { RoomEvent } from '../utils/interfaces/auctionInterface'
import { syncClock } from './api'

export interface AuctionSocketCallbacks {
  onConnectionChange: (connected: boolean) => void
  onEvent: (event: RoomEvent) => void
}

/**
 * Conecta ao WebSocket da sala (/ws/auctions/{id}/) com reconexão
 * automática, backoff exponencial (1s, 2s, 4s, máx. 5s - RF24) e resync ao voltar.
 */
export function connectAuctionRoomWs(
  auctionId: string,
  callbacks: AuctionSocketCallbacks,
): () => void {
  let stopped = false
  let attempt = 0
  let hasConnectedBefore = false
  let socket: WebSocket | null = null
  let timer: ReturnType<typeof setTimeout> | undefined

  const sendResync = () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ type: 'resync' }))
      } catch {
        // ignore
      }
    }
  }

  const onVisibilityChange = () => {
    if (document.visibilityState === 'visible') {
      sendResync()
    }
  }
  document.addEventListener('visibilitychange', onVisibilityChange)

  const connect = () => {
    if (stopped) return
    callbacks.onConnectionChange(false)

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    socket = new WebSocket(
      `${protocol}://${window.location.host}/ws/auctions/${encodeURIComponent(auctionId)}/`,
    )

    socket.onopen = () => {
      if (hasConnectedBefore) {
        sendResync()
      }
      hasConnectedBefore = true
    }

    socket.onmessage = (e) => {
      let event: RoomEvent
      try {
        event = JSON.parse(e.data) as RoomEvent
      } catch {
        return
      }
      syncClock(event.server_time)
      if (event.type === 'snapshot') {
        attempt = 0
        callbacks.onConnectionChange(true)
      }
      callbacks.onEvent(event)
    }

    socket.onclose = () => {
      callbacks.onConnectionChange(false)
      if (!stopped) {
        timer = setTimeout(connect, retryDelay(attempt++))
      }
    }

    socket.onerror = () => {
      socket?.close()
    }
  }

  connect()

  return () => {
    stopped = true
    document.removeEventListener('visibilitychange', onVisibilityChange)
    clearTimeout(timer)
    socket?.close()
    callbacks.onConnectionChange(false)
  }
}
