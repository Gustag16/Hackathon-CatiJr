import { clockOffset } from './domain';
export class ApiError extends Error { constructor(public status: number, public data: {code: string; message: string; fields?: Record<string, string[]>; min_bid_cents?: number; retry_after_ms?: number; auction?: import('./domain').Auction}) { super(data.message); } }
let offset = 0;
export const getOffset = () => offset;
export function syncClock(serverTime?: string) { if (serverTime) offset = clockOffset(serverTime); }
export function csrfCookie() { const cookie = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken=')); return cookie ? decodeURIComponent(cookie.substring(10)) : ''; }
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
 const method = (options.method || 'GET').toUpperCase(); const headers = new Headers(options.headers);
 if (['POST', 'PATCH', 'DELETE'].includes(method)) { const csrf = await fetch('/api/auth/csrf', {credentials: 'same-origin'}); if (!csrf.ok) throw new ApiError(csrf.status, {code: 'CSRF_UNAVAILABLE', message: 'Não foi possível conectar ao serviço. Tente novamente.'}); const token = csrfCookie(); if (!token) throw new ApiError(403, {code: 'CSRF_MISSING', message: 'Sua sessão precisa ser atualizada. Tente novamente.'}); headers.set('X-CSRFToken', token); }
 if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
 const response = await fetch(path, {...options, credentials: 'same-origin', headers});
 const data = await response.json().catch(() => null); if (data?.server_time) syncClock(data.server_time);
 if (!response.ok) throw new ApiError(response.status, data?.message ? data : {code: 'SERVICE_UNAVAILABLE', message: 'O serviço de leilões está indisponível. Tente novamente.'});
 if (data === null && response.status !== 204) throw new ApiError(503, {code: 'NOT_CONNECTED', message: 'A API de leilões ainda não está conectada.'});
 return data as T;
}
