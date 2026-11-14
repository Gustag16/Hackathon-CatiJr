export interface Bid {
  id: string
  amount_cents: number
  participant_number?: number
  bidder_label?: string
  created_at: string
}

export interface PendingBidState {
  key: string
  amount_cents: number
}
