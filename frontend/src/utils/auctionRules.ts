import type {
  Auction,
  ConfigLimits,
} from './interfaces/auctionInterface'
import type { Bid } from './interfaces/bidInterface'
import type { User } from './interfaces/userInterface'

const CATEGORY_NAMES: Record<string, string> = {
  automoveis: 'Automóveis',
  moveis: 'Móveis',
  eletronicos: 'Eletrônicos',
  arte: 'Arte',
  'hobbies-e-musica': 'Hobbies e música',
  colecionaveis: 'Colecionáveis',
  outros: 'Outros',
}

export const ALL_CATEGORY_LABELS = Object.values(CATEGORY_NAMES)

export function categoryLabel(category: string): string {
  return CATEGORY_NAMES[category] ?? category
}

export function formatBidderLabel(bid: Bid): string {
  const label = bid.bidder_label || 'Participante'
  if (label.includes('#')) return label
  if (bid.participant_number !== undefined && bid.participant_number !== null) {
    return `${label} #${bid.participant_number}`
  }
  return label
}

export function formatLeaderText(
  auction: Pick<Auction, 'leader_label' | 'leader_number'>,
): string {
  if (auction.leader_label) {
    const label = auction.leader_label.includes('#')
      ? auction.leader_label
      : auction.leader_number
        ? `${auction.leader_label} #${auction.leader_number}`
        : auction.leader_label
    return `${label} lidera`
  }
  if (auction.leader_number !== null && auction.leader_number !== undefined) {
    return `Participante #${auction.leader_number} lidera`
  }
  return 'Aguardando o primeiro lance'
}

export function bidsLabel(count: number): string {
  if (count === 0) return 'Sem lances'
  return count === 1 ? '1 lance' : `${count} lances`
}

const brlFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

export function money(cents: number): string {
  return brlFormatter.format((cents || 0) / 100)
}

export function toCents(input: string): number {
  const clean = input.trim().replace(/R\$\s*/g, '')
  const normalized = clean.includes(',')
    ? clean.replace(/\./g, '').replace(',', '.')
    : clean
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) {
    throw new Error('Informe um valor válido, com no máximo duas casas decimais.')
  }
  const [whole, fraction = ''] = normalized.split('.')
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
  if (!Number.isSafeInteger(cents) || cents <= 0) {
    throw new Error('Informe um valor maior que zero.')
  }
  return cents
}

export const clockOffset = (serverTime: string, now = Date.now()) =>
  new Date(serverTime).getTime() - now

export const remaining = (end: string, offset: number, now = Date.now()) =>
  Math.max(0, new Date(end).getTime() - (now + offset))

export const canCancel = (auction: Auction, user: User | null) =>
  user?.id === auction.seller.id &&
  (auction.status === 'scheduled' ||
    (auction.status === 'running' && auction.bid_count === 0))

export const retryDelay = (attempt: number) =>
  Math.min(1000 * 2 ** attempt, 5000)

export const definitiveBidResponse = (status: number) =>
  status === 201 || status === 409

/**
 * Gera um UUID v4 válido mesmo em contextos HTTP sem HTTPS (como o IP da VM da banca),
 * onde `crypto.randomUUID` fica indisponível no navegador.
 */
export function generateUUID(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID()
  }
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.getRandomValues === 'function'
  ) {
    const bytes = new Uint8Array(16)
    crypto.getRandomValues(bytes)
    bytes[6] = (bytes[6] & 0x0f) | 0x40 // versão 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80 // variante RFC 4122
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'))
    return `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-${hex[4]}${hex[5]}-${hex[6]}${hex[7]}-${hex[8]}${hex[9]}-${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export function validatePhotos(
  photos: File[],
  limits?: Partial<ConfigLimits>,
): string | null {
  const minPhotos = limits?.min_photos ?? 3
  const maxPhotos = limits?.max_photos ?? 8
  const maxBytes = limits?.max_photo_bytes ?? 5 * 1024 * 1024
  const acceptedTypes = limits?.accepted_photo_types ?? [
    'image/jpeg',
    'image/png',
    'image/webp',
  ]

  if (photos.length < minPhotos || photos.length > maxPhotos) {
    return `Selecione de ${minPhotos} a ${maxPhotos} fotos.`
  }
  const maxMb = Math.round((maxBytes / (1024 * 1024)) * 10) / 10
  if (
    photos.some((f) => !acceptedTypes.includes(f.type) || f.size > maxBytes)
  ) {
    return `Use imagens nos formatos aceitos (${acceptedTypes.join(', ')}) de até ${maxMb} MB.`
  }
  return null
}
