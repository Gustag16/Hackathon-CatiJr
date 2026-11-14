export type Status = 'running' | 'scheduled' | 'sold' | 'ended_no_bids' | 'cancelled';
export interface User { id: string; display_name: string; email: string; created_at: string }
export interface Auction { id: string; item_id: string; name: string; category: string; cover_photo_url: string; status: Status; starts_at: string; ends_at: string; current_price_cents: number; bid_count: number; seller: Pick<User, 'id' | 'display_name' | 'created_at'>; description?: string; photos?: {id: string; url: string}[]; start_price_cents?: number; min_next_bid_cents?: number; leader_number?: number | null; leader_label?: string; result?: Result | null }
export interface Result { status: Status; winner_label: string | null; final_price_cents: number }
export interface Bid { id: string; amount_cents: number; participant_number: number; bidder_label?: string; created_at: string }
export interface AuctionPage { results: Auction[]; page: number; page_size: number; total: number; server_time: string }
export function money(cents: number) { return new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format(cents / 100); }
export function toCents(input: string): number { const clean = input.trim().replace(/R\$\s*/g, ''); const normalized = clean.includes(',') ? clean.replace(/\./g, '').replace(',', '.') : clean; if (!/^\d+(\.\d{1,2})?$/.test(normalized)) throw new Error('Informe um valor válido, com no máximo duas casas decimais.'); const [whole, fraction = ''] = normalized.split('.'); const cents = Number(whole) * 100 + Number(fraction.padEnd(2, '0')); if (!Number.isSafeInteger(cents) || cents <= 0) throw new Error('Informe um valor maior que zero.'); return cents; }
export const clockOffset = (serverTime: string, now = Date.now()) => new Date(serverTime).getTime() - now;
export const remaining = (end: string, offset: number, now = Date.now()) => Math.max(0, new Date(end).getTime() - (now + offset));
export const canCancel = (auction: Auction, user: User | null) => user?.id === auction.seller.id && (auction.status === 'scheduled' || (auction.status === 'running' && auction.bid_count === 0));
export const retryDelay = (attempt: number) => Math.min(1000 * 2 ** attempt, 5000);
export const definitiveBidResponse = (status: number) => status === 201 || status === 409;
export function validatePhotos(photos: File[]) { if (photos.length < 3 || photos.length > 8) return 'Selecione de 3 a 8 fotos.'; if (photos.some(f => !['image/jpeg', 'image/png', 'image/webp'].includes(f.type) || f.size > 5 * 1024 * 1024)) return 'Use imagens JPEG, PNG ou WebP de até 5 MB.'; return null; }
