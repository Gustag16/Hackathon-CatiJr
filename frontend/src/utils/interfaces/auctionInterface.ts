import type { Bid } from './bidInterface'
import type { PublicUser } from './userInterface'

export type AuctionStatus =
  | 'running'
  | 'scheduled'
  | 'sold'
  | 'ended_no_bids'
  | 'cancelled'

export interface AuctionResult {
  status: AuctionStatus
  winner_label: string | null
  final_price_cents: number | null
}

export interface AuctionPhoto {
  id: string
  url: string
}

export interface Auction {
  id: string
  item_id: string
  name: string
  category: string
  cover_photo_url: string
  status: AuctionStatus
  starts_at: string
  ends_at: string
  original_ends_at?: string
  current_price_cents: number
  bid_count: number
  seller: PublicUser
  description?: string
  photos?: AuctionPhoto[]
  start_price_cents?: number
  min_next_bid_cents?: number
  leader_number?: number | null
  leader_label?: string | null
  result?: AuctionResult | null
  server_time?: string
}

export interface AuctionPage {
  results: Auction[]
  page: number
  page_size: number
  total: number
  server_time: string
}

export interface CategoryOption {
  id: string
  name: string
}

export interface ConfigLimits {
  min_photos: number
  max_photos: number
  max_photo_bytes: number
  accepted_photo_types: string[]
  max_name_length: number
  max_description_length: number
  max_display_name_length?: number
  min_duration_seconds: number
  max_duration_seconds: number
  min_start_delay_seconds: number
  max_start_advance_seconds: number
}

export interface ConfigResponse {
  categories: CategoryOption[]
  limits: ConfigLimits
  server_time: string
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  db: boolean
  redis: boolean
  server_time: string
}

export interface BidAcceptedResponse {
  bid: Bid
  auction: Auction
  you: {
    participant_number: number
  }
}

export interface ApiErrorPayload {
  code: string
  message: string
  fields?: Record<string, string[]>
  reason?: string
  min_bid_cents?: number
  retry_after_ms?: number
  auction?: Auction
}

export interface RoomEvent {
  type: string
  server_time: string
  auction: Partial<Auction>
  you?: { participant_number: number | null }
  recent_bids?: Bid[]
  bid?: Bid
  extended?: boolean
  previous_leader_number?: number | null
  result?: AuctionResult | null
}
