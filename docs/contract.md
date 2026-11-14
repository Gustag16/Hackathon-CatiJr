# Contrato da API e do WebSocket — v1.2

v1.2 de 14/11/2026. O que mudou desde a v0 está nas seções 7 a 9. Decisões e seu status, na seção 6.
Qualquer mudança neste arquivo é avisada no grupo ANTES de mexer no código.

## 1. Convenções

- REST em `/api`, WebSocket em `/ws`, fotos em `/media`. Tudo na mesma origem (Caddy na 8080). Sem CORS.
- JSON UTF-8, campos em `snake_case`, IDs em UUID (string).
- **Dinheiro**: inteiro em centavos, campo termina em `_cents` (R$ 12,50 = `1250`). Nunca float. (D1, confirmado)
- **Datas**: ISO 8601 UTC com `Z` (`2026-11-14T18:30:00Z`). O front converte para o fuso de quem vê.
- **Sincronia de tempo**: todo objeto de estado de leilão traz `server_time`. O front calcula
  `offset = server_time - Date.now()` ao receber e mostra o cronômetro com `ends_at - (Date.now() + offset)`.
  O servidor NUNCA envia "ticks" de contagem regressiva. O contador é só visual (RF16).
- **Autenticação**: cookie de sessão Django (`sessionid`, HttpOnly) + CSRF. Sessão de 1 hora com
  expiração deslizante (renova a cada uso). O front chama `GET /api/auth/csrf` uma vez e envia o
  cookie `csrftoken` no header `X-CSRFToken` em todo POST/PATCH/DELETE. Sessão expirada = `401`. (D2)
- **Erros**: sempre `{ "code": "...", "message": "...", ...extras }`.

| code | HTTP | quando |
|---|---|---|
| `NOT_AUTHENTICATED` | 401 | sem sessão ou sessão expirada |
| `INVALID_CREDENTIALS` | 401 | login errado |
| `FORBIDDEN` | 403 | logado, mas sem permissão (ex.: não é o comitente) |
| `NOT_FOUND` | 404 | recurso inexistente |
| `VALIDATION_ERROR` | 400 | corpo inválido; traz `fields: { campo: ["mensagem"] }` |
| `EMAIL_TAKEN` | 409 | e-mail já cadastrado (comparação sem maiúsculas e sem espaços nas pontas) |
| `CANNOT_CANCEL` | 409 | leilão com lances, já finalizado etc.; traz `reason` |
| `RATE_LIMITED` | 429 | (Nível 2, RF13) traz `retry_after_ms` |

Erros específicos de lance: seção 4.

## 2. Objetos

No banco, **Item** (nome, descrição, categoria, fotos) e **Leilão** (início, duração, preço inicial)
são entidades separadas: um item pode ter vários leilões ao longo do tempo (RF28). Na API o leilão
vem "achatado" com os campos do item, mais `item_id`.

**User** `{ id, display_name, email, created_at }` (e-mail só para o próprio usuário)

**PublicUser** `{ id, display_name, created_at }`

**status**: `scheduled | running | sold | ended_no_bids | cancelled`

**AuctionPublic** (qualquer visitante pode ver):
```json
{
  "id": "uuid", "item_id": "uuid", "status": "running",
  "starts_at": "2026-11-14T18:00:00Z",
  "ends_at": "2026-11-14T18:30:00Z",
  "original_ends_at": "2026-11-14T18:30:00Z",
  "current_price_cents": 12000,
  "min_next_bid_cents": 12500,
  "bid_count": 7,
  "server_time": "2026-11-14T18:12:03Z"
}
```
Antes do primeiro lance, `current_price_cents = start_price_cents` e `min_next_bid_cents = start_price_cents`
(o primeiro lance pode ser igual ao preço inicial, RF14). Depois, o mínimo é calculado só pelo servidor.

**AuctionState** (só dentro da sala e nas respostas de lance, ou seja, para logados) =
AuctionPublic + `{ leader_number: int | null, leader_label: "Dan*** #3" | null }`.

**Rótulo anônimo (RF09, D4).** Cada participante recebe um número por leilão, atribuído no seu 1º lance aceito
naquele leilão, sob a mesma trava do lance. O rótulo é o nome mascarado + `#número`: mostra os primeiros
`max(1, min(3, ⌊tamanho do nome / 2⌋))` caracteres e depois `***` ("Danilo" → `Dan*** #3`, "Gus" → `G*** #3`).
A API NUNCA expõe o id do usuário líder. O front sabe se VOCÊ lidera comparando `leader_number` com
`you.participant_number` (devolvido no `snapshot` e na resposta do lance) e pode escrever "Você" no lugar do rótulo.

**Bid** `{ id, amount_cents, bidder_label, created_at }`

**AuctionSummary** (listagem): `{ id, item_id, name, category, cover_photo_url, status, starts_at, ends_at, current_price_cents, bid_count, seller: PublicUser }`

**AuctionDetail** = AuctionSummary + AuctionPublic + `{ description, photos: [{id, url}], start_price_cents, result: null | { status, winner_label, final_price_cents } }`.
O detalhe público NÃO traz líder nem lances recentes: isso é conteúdo da sala (login). (RF04)

Fotos: `url` relativa (`/media/...`), servida pelo Caddy direto do disco da VM.

## 3. REST

### Configuração
| Método | Caminho | Auth | Resposta |
|---|---|---|---|
| GET | `/api/config` | não | `{ categories: [{id,name}], limits: { min_photos, max_photos, max_photo_bytes, accepted_photo_types, max_name_length, max_description_length, min_duration_seconds, max_duration_seconds, min_start_delay_seconds, max_start_advance_seconds }, server_time }` |

O front usa `limits` para validar no formulário igual ao servidor (RF05/RF06).

Categorias (fixas no backend; `id` = slug): `automoveis` Automóveis · `moveis` Móveis · `eletronicos` Eletrônicos · `arte` Arte · `hobbies-e-musica` Hobbies e música · `colecionaveis` Colecionáveis · `outros` Outros.

### Contas
| Método | Caminho | Auth | Corpo | Sucesso | Erros |
|---|---|---|---|---|---|
| GET | `/api/auth/csrf` | não | — | 204 (seta cookie `csrftoken`) | — |
| POST | `/api/auth/register` | não | `{display_name, email, password}` | 201 `User` (não loga) | `VALIDATION_ERROR`, `EMAIL_TAKEN` |
| POST | `/api/auth/login` | não | `{email, password}` | 200 `{ user }` | `INVALID_CREDENTIALS` |
| POST | `/api/auth/logout` | sim | — | 204 | — |
| GET | `/api/auth/me` | sim | — | 200 `User` | `NOT_AUTHENTICATED` |

Todo usuário logado pode anunciar e dar lance (RF03). Não existe administrador.

### Leilões
| Método | Caminho | Auth | Corpo / Query | Sucesso | Erros |
|---|---|---|---|---|---|
| GET | `/api/auctions` | não | `?status=running,scheduled&page=1&page_size=12` (Nível 2: `&q=&category=`) | 200 `{ results: AuctionSummary[], page, page_size, total, server_time }` | — |
| GET | `/api/auctions/{id}` | não | — | 200 `AuctionDetail` | `NOT_FOUND` |
| POST | `/api/auctions` | sim | `multipart/form-data`: `name, description, category, start_price_cents, starts_at, duration_seconds, photos` (arquivo, repetido, de `min_photos` a `max_photos`) | 201 `AuctionDetail` (cria o Item e o 1º Leilão) | `VALIDATION_ERROR` |
| POST | `/api/auctions/{id}/cancel` | sim (comitente) | — | 200 `AuctionDetail` | `FORBIDDEN`, `CANNOT_CANCEL` (`reason`: `HAS_BIDS` \| `ALREADY_FINISHED`) |

**Listagem (RF20).** Só entram leilões `scheduled` e `running`; os finalizados ficam acessíveis pelo link direto.
- `status`: `running`, `scheduled` ou `running,scheduled` (padrão). A tela usa isso nas abas
  "Em andamento", "Agendados" e "Todos".
- **Ordem, decidida pelo servidor (o front não reordena):** `running` primeiro, por `ends_at` crescente;
  depois `scheduled`, por `starts_at` crescente; desempate por `id`.
- **Paginação numerada:** `page` (a partir de 1) e `page_size` (padrão **12**, máximo **48**); `total` permite
  montar "Página 1 de N". Índices no banco: `(status, ends_at)` e `(status, starts_at)`.
- Cada item é um `AuctionSummary`. O front mostra "Lance inicial" quando `bid_count = 0` (aí
  `current_price_cents` = preço inicial) e "Atual" caso contrário. Sem líder no cartão (isso é da sala, RF04).
- A tela refaz a consulta a cada 30 s; a listagem não usa WebSocket.

Nível 2 (reservado, ainda sem formato): `PATCH /api/auctions/{id}` (RF23), `POST /api/auctions/{id}/relist`
(RF28; cria um novo Leilão para o MESMO Item), `GET /api/me/participations` (RF27),
`GET /api/users?q=` e `GET /api/users/{id}` (RF22).

## 4. Lances

`POST /api/auctions/{id}/bids` — auth: sim.
Headers: `Idempotency-Key: <uuid>` (obrigatório) e `X-CSRFToken`. Corpo: `{ "amount_cents": 12500 }`

**Aceito** — `201`:
```json
{ "bid": { "id": "uuid", "amount_cents": 12500, "bidder_label": "Dan*** #3", "created_at": "..." },
  "auction": { /* AuctionState */ },
  "you": { "participant_number": 3 } }
```

**Recusa de negócio** — `409` com `{ code, message, auction: AuctionState }` (+ `min_bid_cents` em `BID_TOO_LOW`):

| code | quando |
|---|---|
| `AUCTION_NOT_RUNNING` | `scheduled` ou já finalizado/cancelado |
| `AUCTION_ENDED` | `running`, mas `now >= ends_at` (o worker ainda não fechou) |
| `IS_SELLER` | comitente tentando dar lance no próprio leilão |
| `IS_LEADER` | já é o líder |
| `BID_TOO_LOW` | abaixo do mínimo vigente AGORA; traz `min_bid_cents` |

Outros: `401 NOT_AUTHENTICATED`, `404 NOT_FOUND`, `400 VALIDATION_ERROR` (valor ou chave inválidos),
`422 IDEMPOTENCY_KEY_MISMATCH`, `429 RATE_LIMITED` (Nível 2).
Todo lance recusado informa o motivo e o lance mínimo atual (RF10). Lance é irrevogável.

**Ordem das verificações** (o primeiro que falha define o código):
1. sessão (401) → 2. leilão existe (404) → 3. corpo e chave válidos (400)
4. chave já vista: replay ou `IDEMPOTENCY_KEY_MISMATCH` (422)
5. limite de frequência (429, Nível 2)
6. `AUCTION_NOT_RUNNING` / `AUCTION_ENDED` → 7. `IS_SELLER` → 8. `IS_LEADER` → 9. `BID_TOO_LOW`

**Tempo**: o lance só é válido se `now < ends_at`, com `now` = relógio do servidor dentro da transação.
O worker fecha quando `now >= ends_at`. Assim não há lacuna nem sobreposição.

**Prorrogação (RF15)**: se, no lance aceito, `ends_at - now < 2 min`, então
`ends_at = min(now + 2 min, original_ends_at + 30 min)`. Nesse caso o evento WS traz `extended: true`.

### Idempotência (RF12)
- O front gera a chave (`crypto.randomUUID()`) ao PREPARAR um lance.
- O servidor guarda, por `(usuário, chave)`, a impressão digital `(auction_id, amount_cents)` e o resultado
  **definitivo**: o `201` e os `409`. Só esses são gravados.
- **Mesma chave + mesmo `(auction_id, amount_cents)`** = replay: devolve o MESMO status, o MESMO `code`/`message`/`bid`
  originais, mais um `auction` ATUAL (e `min_bid_cents` atual em `BID_TOO_LOW`), com o header
  `Idempotent-Replay: true`. Nunca cria um 2º lance.
- **Mesma chave + outro leilão ou outro valor** = `422 IDEMPOTENCY_KEY_MISMATCH`.
- Respostas **não definitivas**: `401`, `429`, `5xx` e falha de rede. Nesses casos o front reenvia o MESMO lance
  com a MESMA chave (depois de logar de novo, no caso do 401). `429` nunca é gravado como resultado.
- Depois de um `201` ou `409`, o PRÓXIMO lance usa chave NOVA. Se o usuário muda o valor, é chave nova.

### Limite de frequência (Nível 2, RF13)
Por usuário (nunca por IP, para usuários diferentes não se bloquearem), mínimo de 500 ms entre lances do mesmo
usuário. Replay é checado ANTES do limite, então o reenvio legítimo não é punido.

## 5. WebSocket da sala

URL: `/ws/auctions/{id}/`. Autentica pelo cookie de sessão. Fechamento: `4401` sem sessão · `4404` leilão inexistente.
Pode-se entrar na sala de um leilão `scheduled` (para ver o `auction_started` ao vivo), `running` ou já finalizado
(o `snapshot` traz o resultado). No Núcleo todo usuário logado entra como participante, inclusive o comitente
(ele vê a sala e leva `IS_SELLER` se tentar dar lance). Espectador e presença: Nível 2.

### Servidor → cliente
Todas as mensagens: `{ "type": "...", ..., "server_time": "..." }`

| type | campos | quando |
|---|---|---|
| `snapshot` | `auction: AuctionState`, `you: { participant_number }`, `recent_bids: Bid[]` (até 10, mais novo primeiro), `result` (se finalizado) | ao conectar e após `resync` |
| `bid_accepted` | `bid: Bid`, `auction: AuctionState`, `extended: bool` | após o COMMIT de um lance (nunca antes) |
| `auction_started` | `auction: AuctionState` | worker abriu o leilão |
| `auction_finished` | `auction: AuctionState`, `result: {status, winner_label, final_price_cents}` | fechou (`sold` ou `ended_no_bids`) |
| `auction_cancelled` | `auction: AuctionState` | comitente cancelou |
| `error` | `code`, `message` | mensagem inválida do cliente |
| `presence` | `participants`, `spectators` | (Nível 2, RF25) |
| `outbid` | `auction_id`, `your_bid_cents`, `new_price_cents` | só para quem foi superado (Nível 2, RF26) |

Prorrogação: com `extended = true` o `ends_at` novo vem em `auction`; o cronômetro só recalcula com o novo `ends_at`.

### Cliente → servidor
| type | campos | efeito |
|---|---|---|
| `resync` | — | pede novo `snapshot` |
| `ping` | — | servidor responde `{type:"pong"}` |
| `set_role` | `role: "participant" \| "spectator"` | (Nível 2, RF25) |

Lances NÃO vão pelo WebSocket: são POST HTTP (seção 4).

### Reconexão (RF24)
No `onclose`, reconectar com backoff (1s, 2s, 4s…, máx. 5s). No `onopen` o servidor já envia `snapshot`.
Enquanto desconectado, o front mostra "reconectando…" e desabilita o botão de lance.

## 6. Decisões

| # | Decisão | Status |
|---|---|---|
| D1 | Dinheiro em centavos inteiros | **Confirmado** |
| D2 | Sessão Django + CSRF, 1 h deslizante | Proposto |
| D3 | "Estar na sala" (RF10) = sessão válida; a sala exige login. Sem presença por WS | Proposto |
| D4 | `leader_label` = nome mascarado + nº do participante no leilão (ex.: `Dan*** #3`); a API não expõe o id do líder | **Confirmado** |
| D5 | Fotos no disco local da VM (adendo da organização ao PDF), volume Docker servido pelo Caddy, só o caminho no banco | **Confirmado** |
| D6 | Limites: nome ≤ 100, descrição ≤ 2000, 3–8 fotos jpeg/png/webp ≤ 5 MB, duração ≥ 60 s, início ≥ 30 s à frente; categorias: Automóveis, Móveis, Eletrônicos, Arte, Hobbies e música, Colecionáveis, Outros | Proposto |
| D7 | Listagem (RF20): grade de cartões, abas Em andamento/Agendados/Todos, ordem por término (andamento) e início (agendados), 12 por página numerada, atualiza a cada 30 s | Proposto |

## 7. O que mudou da v0 para a v1

- Item e Leilão separados no banco; `item_id` na API; `relist` cria novo Leilão do mesmo Item.
- `PublicUser` ganhou `created_at`. `limits` ganhou `max_name_length` e `max_description_length`.
- Detalhe público sem líder e sem lances recentes (isso é da sala). `AuctionPublic` x `AuctionState`.
- Login não devolve mais `session_expires_at`.
- Removido `NOT_IN_ROOM`. Sem `?role=` no Núcleo; comitente entra como participante.
- Idempotência: só 201 e 409 são definitivos; 401/429/5xx/rede reenviam com a MESMA chave; replay devolve `auction` atual;
  `IDEMPOTENCY_KEY_MISMATCH` compara `auction_id` e `amount_cents` (422).
- Ordem das verificações, regra `now < ends_at` e fórmula da prorrogação explícitas. `RATE_LIMITED` na seção de lances.
- Fotos locais (D5): `url` relativa `/media/...`.

## 8. O que mudou da v1 para a v1.1

- Listagem definida (RF20, D7): padrão `status=running,scheduled`, `page_size` padrão 12 (máx. 48), ordem fixa por status e por data, índices e atualização a cada 30 s.

## 9. O que mudou da v1.1 para a v1.2

- D4 decidido: rótulo = nome mascarado + nº do participante por leilão (`Dan*** #3`). `leader_id` saiu de `AuctionState` (ninguém é identificável entre leilões); entrou `leader_number`; `you.participant_number` vem no `snapshot` e na resposta do lance.
- D6: categorias definidas (7, com "Outros"). Início mínimo do leilão agora 30 s (antes 60 s): com 60 s, "abrir em 1 minuto" (RF06) era recusado.
