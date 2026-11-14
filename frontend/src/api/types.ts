// Tipos oficiais do Contrato v1.3 (docs/contract.md)

export type AuctionStatus =
  | 'scheduled'
  | 'running'
  | 'sold'
  | 'ended_no_bids'
  | 'cancelled'

export interface User {
  id: string
  display_name: string
  email: string
  created_at: string
}

export interface PublicUser {
  id: string
  display_name: string
  created_at: string
}

export interface AuctionPublic {
  id: string
  item_id: string
  status: AuctionStatus
  starts_at: string
  ends_at: string
  original_ends_at: string
  current_price_cents: number
  min_next_bid_cents: number
  bid_count: number
  server_time: string
}

export interface AuctionState extends AuctionPublic {
  leader_number: number | null
  leader_label: string | null
}

export interface Bid {
  id: string
  amount_cents: number
  bidder_label: string
  created_at: string
}

export interface AuctionSummary {
  id: string
  item_id: string
  name: string
  category: string
  cover_photo_url: string
  status: AuctionStatus
  starts_at: string
  ends_at: string
  current_price_cents: number
  bid_count: number
  seller: PublicUser
}

export interface AuctionPhoto {
  id: string
  url: string
}

export interface AuctionResult {
  status: AuctionStatus
  winner_label: string | null
  final_price_cents: number | null
}

export interface AuctionDetail extends AuctionSummary, AuctionPublic {
  description: string
  photos: AuctionPhoto[]
  start_price_cents: number
  result: AuctionResult | null
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

export interface AuctionListResponse {
  results: AuctionSummary[]
  page: number
  page_size: number
  total: number
  server_time: string
}

export interface BidAcceptedResponse {
  bid: Bid
  auction: AuctionState
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
  auction?: AuctionState
}
