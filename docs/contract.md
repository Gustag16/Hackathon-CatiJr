# Contrato da API e do WebSocket — v0 (PROPOSTA para revisão dos três)

Itens marcados com ⚠️ dependem de decisão da equipe (ver "Decisões em aberto" no fim).
Qualquer mudança neste arquivo é avisada no grupo ANTES de mexer no código.

## 1. Convenções

- REST em `/api`, WebSocket em `/ws`. Tudo na mesma origem (Caddy na 8080). Sem CORS.
- JSON UTF-8, campos em `snake_case`, IDs em UUID (string).
- **Dinheiro**: inteiro em centavos, campo termina em `_cents` (R$ 12,50 = `1250`). ⚠️ D1
- **Datas**: ISO 8601 UTC com `Z` (`2026-11-14T18:30:00Z`). O front converte para o fuso de quem vê.
- **Sincronia de tempo**: todo objeto de estado de leilão traz `server_time`. O front
  calcula `offset = server_time - Date.now()` ao receber e mostra o cronômetro com
  `ends_at - (Date.now() + offset)`. O servidor NUNCA envia "ticks" de contagem regressiva.
  O contador é só visual: quem decide se um lance é válido é o servidor (RF16).
- **Autenticação**: cookie de sessão Django (`sessionid`, HttpOnly) + CSRF. ⚠️ D2
  O front chama `GET /api/auth/csrf` uma vez; depois envia o cookie `csrftoken` no header
  `X-CSRFToken` em todo POST/PATCH/DELETE. A sessão renova com o uso (expiração deslizante).
- **Erros**: sempre `{ "code": "...", "message": "...", ...extras }` com o HTTP status abaixo.

| code | HTTP | quando |
|---|---|---|
| `NOT_AUTHENTICATED` | 401 | sem sessão ou sessão expirada |
| `INVALID_CREDENTIALS` | 401 | login errado |
| `FORBIDDEN` | 403 | logado, mas sem permissão (ex.: não é o comitente) |
| `NOT_FOUND` | 404 | recurso inexistente |
| `VALIDATION_ERROR` | 400 | corpo inválido; traz `fields: { campo: ["mensagem"] }` |
| `EMAIL_TAKEN` | 409 | e-mail já cadastrado |
| `CANNOT_CANCEL` | 409 | leilão com lances, já finalizado etc.; traz `reason` |
| `RATE_LIMITED` | 429 | (Nível 2, RF13) traz `retry_after_ms` |

Erros específicos de lance estão na seção 4.

## 2. Objetos

**User** `{ id, display_name, email, created_at }` (e-mail só para o próprio usuário)

**PublicUser** `{ id, display_name }`

**Estados do leilão** (`status`): `scheduled | running | sold | ended_no_bids | cancelled`

**AuctionState** (usado em REST e WS):
```json
{
  "id": "uuid",
  "status": "running",
  "starts_at": "2026-11-14T18:00:00Z",
  "ends_at": "2026-11-14T18:30:00Z",
  "original_ends_at": "2026-11-14T18:30:00Z",
  "current_price_cents": 12000,
  "min_next_bid_cents": 12500,
  "bid_count": 7,
  "leader_id": "uuid | null",
  "leader_label": "Dan*** | null",
  "server_time": "2026-11-14T18:12:03Z"
}
```
`min_next_bid_cents` é calculado só pelo servidor (RF14). O primeiro lance pode ser
igual ao preço inicial. `leader_label` não expõe o nome completo (RF09). ⚠️ D4

**Bid** `{ id, amount_cents, bidder_label, created_at }`

**AuctionSummary** (listagem):
`{ id, name, category, cover_photo_url, status, starts_at, ends_at, current_price_cents, bid_count, seller: PublicUser }`

**AuctionDetail** = AuctionSummary + AuctionState + `{ description, photos: [{id, url}], start_price_cents, recent_bids: Bid[] (até 10, mais novo primeiro), result: null | { status, winner_label, final_price_cents } }`

## 3. REST

### Configuração
| Método | Caminho | Auth | Resposta |
|---|---|---|---|
| GET | `/api/config` | não | `{ categories: [{id,name}], limits: { min_photos, max_photos, max_photo_bytes, accepted_photo_types, min_duration_seconds, max_duration_seconds, min_start_delay_seconds, max_start_advance_seconds }, server_time }` |

O front usa `limits` para validar no formulário igual ao servidor (RF05/RF06).

### Contas
| Método | Caminho | Auth | Corpo | Sucesso | Erros |
|---|---|---|---|---|---|
| GET | `/api/auth/csrf` | não | — | 204 (seta cookie `csrftoken`) | — |
| POST | `/api/auth/register` | não | `{display_name, email, password}` | 201 `User` (não loga) | `VALIDATION_ERROR`, `EMAIL_TAKEN` |
| POST | `/api/auth/login` | não | `{email, password}` | 200 `{ user, session_expires_at }` | `INVALID_CREDENTIALS` |
| POST | `/api/auth/logout` | sim | — | 204 | — |
| GET | `/api/auth/me` | sim | — | 200 `User` | `NOT_AUTHENTICATED` |

Todo usuário logado pode anunciar e dar lance (RF03). Não existe administrador.

### Leilões
| Método | Caminho | Auth | Corpo / Query | Sucesso | Erros |
|---|---|---|---|---|---|
| GET | `/api/auctions` | não | `?status=scheduled,running&page=1&page_size=20` (Nível 2: `&q=&category=`) | 200 `{ results: AuctionSummary[], page, page_size, total, server_time }` | — |
| GET | `/api/auctions/{id}` | não | — | 200 `AuctionDetail` | `NOT_FOUND` |
| POST | `/api/auctions` | sim | `multipart/form-data`: `name, description, category, start_price_cents, starts_at, duration_seconds, photos` (arquivo, repetido ≥ `min_photos`) | 201 `AuctionDetail` | `VALIDATION_ERROR` |
| POST | `/api/auctions/{id}/cancel` | sim (comitente) | — | 200 `AuctionDetail` | `FORBIDDEN`, `CANNOT_CANCEL` (`reason`: `HAS_BIDS` \| `ALREADY_FINISHED`) |

Nível 2 (reservado, ainda sem formato): `PATCH /api/auctions/{id}` (RF23), `POST /api/auctions/{id}/relist` (RF28),
`GET /api/me/participations` (RF27), `GET /api/users?q=` e `GET /api/users/{id}` (RF22).

## 4. Lances

`POST /api/auctions/{id}/bids` — auth: sim.
Headers: `Idempotency-Key: <uuid>` (obrigatório) e `X-CSRFToken`. Corpo: `{ "amount_cents": 12500 }`

**Aceito** — `201`:
```json
{ "bid": { "id": "uuid", "amount_cents": 12500, "bidder_label": "Dan***", "created_at": "..." },
  "auction": { /* AuctionState */ } }
```

**Recusado** — `409` (ou `401`/`403`) com `{ code, message, auction: AuctionState }`:

| code | quando |
|---|---|
| `BID_TOO_LOW` | abaixo do mínimo vigente agora; traz `min_bid_cents` |
| `AUCTION_NOT_RUNNING` | `scheduled` ou já finalizado/cancelado |
| `AUCTION_ENDED` | passou do `ends_at` (horário do servidor) |
| `IS_SELLER` | comitente tentando dar lance no próprio leilão |
| `IS_LEADER` | já é o líder |
| `NOT_IN_ROOM` | não está na sala como participante ⚠️ D3 |
| `NOT_AUTHENTICATED` | sessão expirada |
| `IDEMPOTENCY_KEY_MISMATCH` | mesma chave com `amount_cents` diferente |

Todo lance recusado informa o motivo e o lance mínimo atual (RF10). Lance é irrevogável.

**Reenvio (RF12)**: a mesma `Idempotency-Key` devolve o resultado ORIGINAL (mesmo status
e mesmo corpo, aceito OU recusado) com o header `Idempotent-Replay: true`, e nunca cria
um 2º lance. Regras para o front:
- gere a chave (`crypto.randomUUID()`) ao PREPARAR um lance;
- reenvie com a MESMA chave só se for o mesmo envio (rede caiu, clique duplo);
- após uma resposta definitiva (aceito ou recusado), o próximo lance usa chave NOVA.

## 5. WebSocket da sala

URL: `/ws/auctions/{id}/?role=participant|spectator` (padrão `participant`; o comitente
só entra como `spectator`). Autentica pelo cookie de sessão.
Fechamento: `4401` sem sessão · `4404` leilão inexistente.

### Servidor → cliente
Todas as mensagens: `{ "type": "...", ... , "server_time": "..." }`

| type | campos | quando |
|---|---|---|
| `snapshot` | `auction: AuctionState`, `recent_bids: Bid[]`, `presence: {participants, spectators}` | ao conectar e após `resync` |
| `bid_accepted` | `bid: Bid`, `auction: AuctionState`, `extended: bool` | após o COMMIT de um lance (nunca antes) |
| `auction_started` | `auction: AuctionState` | worker abriu o leilão |
| `auction_finished` | `auction: AuctionState`, `result: {status, winner_label, final_price_cents}` | fechou (`sold` ou `ended_no_bids`) |
| `auction_cancelled` | `auction: AuctionState` | comitente cancelou |
| `presence` | `participants`, `spectators` | alguém entrou/saiu/trocou de papel (Nível 2) |
| `outbid` | `auction_id`, `your_bid_cents`, `new_price_cents` | só para quem foi superado (Nível 2, RF26) |
| `error` | `code`, `message` | mensagem inválida do cliente |

Prorrogação: quando `extended = true`, o `ends_at` novo vem em `auction`; o cronômetro
só recalcula com o novo `ends_at`.

### Cliente → servidor
| type | campos | efeito |
|---|---|---|
| `set_role` | `role: "participant" \| "spectator"` | troca de papel sem sair da sala (Nível 2, RF25) |
| `resync` | — | pede novo `snapshot` |
| `ping` | — | mantém a conexão; servidor responde `{type:"pong"}` |

Lances NÃO são enviados pelo WebSocket: são POST HTTP (seção 4).

### Reconexão (RF24)
No `onclose`, reconectar com backoff (1s, 2s, 4s…, máx. 5s). No `onopen` o servidor já
envia `snapshot`. Enquanto desconectado, o front mostra "reconectando…" e desabilita o botão de lance.

## 6. Decisões em aberto (confirmar e registrar em `docs/decisions.md`)

- **D1 Dinheiro:** centavos inteiros (proposto) vs `Decimal(12,2)` serializado como string. Back e front precisam usar o MESMO.
- **D2 Autenticação:** sessão + CSRF (proposto; o WS reaproveita o cookie) vs token/JWT.
- **D3 "Estar na sala" (RF10 cond. 1):** conectado ao WS como `participant` (proposto) vs apenas ter sessão válida (mais simples).
- **D4 `leader_label`:** como identificar o líder sem expor o nome completo (ex.: `"Dan***"`, ou `"Participante 3"` por leilão).
- **D5 Fotos:** upload multipart pelo backend para o storage da organização; tipo do storage (S3-compatível?) a confirmar.
- **D6 Limites:** valores de `limits` (fotos, tamanhos, duração, antecedência) e a lista de categorias.
