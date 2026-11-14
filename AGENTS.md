# Leilão Online — Time Katchau (Hackathon CATI Cloud Labs)

Plataforma web de leilão online em tempo real, hospedada em uma VM. Simulação:
nenhuma transação é real. Este arquivo é a fonte de verdade para humanos E para
qualquer assistente de IA (Claude, Gemini etc.). Leia inteiro antes de editar.

## Regras de trabalho (obrigatórias)
1. Leia `docs/contract.md` antes de tocar em qualquer endpoint ou evento WebSocket.
2. Cada pessoa é dona de uma pasta. NÃO edite a pasta de outro membro; peça a ele.
   - `backend/`  → Danilo (modelos, máquina de estados, motor de lances, worker)
   - `frontend/` → Amadeu (todas as telas)
   - `deploy/` + docker-compose + consumer WebSocket → Bortoleto
3. Mudou o contrato? Avise no grupo ANTES de mexer no código.
4. Registre as decisões da equipe na tabela do `README.md` (seção "Decisões da equipe"),
   com 1–2 frases de justificativa. O PDF exige isso no README e a banca cobra no pitch.
5. Commits pequenos, branch por pessoa, `git pull origin main` de hora em hora.
6. Código gerado por IA só entra se alguém do time consegue explicá-lo. A banca
   escolhe quem responde.

## Stack
- Backend: Python + Django + Django REST Framework + Django Channels (ASGI), PostgreSQL 16
- Channel layer: Redis (fan-out do WebSocket; viabiliza várias instâncias — bônus)
- Tempo real: WebSocket (Channels). Lances são POST HTTP; o WS só transmite estado.
- Frontend: React + Vite + TypeScript + Tailwind (SPA estática)
- Proxy: Caddy na porta 8080 da VM (front em `/`, API em `/api`, WS em `/ws`, fotos em `/media`)
- Fotos: disco LOCAL da VM (adendo da organização: o PDF previa nuvem, foi corrigido).
  `FileSystemStorage` em `MEDIA_ROOT`, que é um volume Docker compartilhado entre o backend
  (grava) e o Caddy (serve `/media/*`). O volume PRECISA sobreviver a reinício e a
  `docker compose down`. Nunca no banco: só o caminho. Nome do arquivo = UUID aleatório;
  validar tipo e tamanho pelo conteúdo, nunca pelo nome enviado.
- Tudo sobe com `docker compose up -d --build`

## Restrições de infraestrutura
- A VM só expõe UMA porta pública, repassada para a 8080 dentro da VM.
- O front DEVE escutar na 8080 (via Caddy). Mesma origem: sem CORS.
- Todos os fluxos devem funcionar pela interface web (sem Postman/console).
- O Django admin NÃO pode ficar acessível em produção (RF03: não existe administrador).

## Modelo de dados
- **Item** (nome, descrição, categoria, fotos) e **Leilão/Auction** (início, duração, preço
  inicial, status) são entidades SEPARADAS. Um item tem vários leilões ao longo do tempo,
  mas nunca mais de um `scheduled`/`running` ao mesmo tempo (RF28).
- Lances, tabela de idempotência `UNIQUE(usuário, chave)` e usuários (e-mail único,
  normalizado em minúsculas e sem espaços).

## Estados do leilão (RN01) — 5 estados, 5 transições
`scheduled` → `running` (chegou o início)
`scheduled` → `cancelled` (comitente, antes do início)
`running` → `cancelled` (comitente, SÓ se não houver lances)
`running` → `sold` (fim, com lances)
`running` → `ended_no_bids` (fim, sem lances)
`sold`, `ended_no_bids` e `cancelled` são finais. Com lances, só termina `sold`.
Toda transição passa por UMA função central; nenhum outro código altera `status`.

## Invariantes que NÃO podem ser violadas (a banca testa)
- Dinheiro: inteiro em CENTAVOS (`*_cents`) no banco e na API, inclusive na tabela de
  incrementos do RF14. Nunca float, nunca `Decimal` na API. (RF19; D1 confirmado)
- Tempo: UTC no banco (`USE_TZ=True`); o horário válido é SEMPRE o do servidor
  (`timezone.now()`). O contador do navegador é só visual. (RF16, RF19)
- Lance: `transaction.atomic()` + `select_for_update()` na linha do leilão, validando
  NO MOMENTO do processamento (lance mínimo vigente agora, não o da tela): sessão
  válida; leilão `running` e `now < ends_at`; autor não é o comitente nem o líder;
  valor >= lance mínimo. (RF10, RF11). Ordem das verificações: ver contrato, seção 4.
- Cancelar e fechar usam a MESMA trava do lance. (RF08, RF18)
- Broadcast SÓ DEPOIS do commit: `transaction.on_commit(...)` ao chamar o `group_send`
  do Channels. A sala nunca vê estado não gravado. (RF11)
- Idempotência (RF12): `Idempotency-Key` (UUID do navegador) por tentativa. Só `201` e
  `409` são gravados (INCLUSIVE recusas). Replay devolve status, `code` e `bid` originais
  + `auction` ATUAL. Chave com outro leilão/valor → `422 IDEMPOTENCY_KEY_MISMATCH`.
  `401`, `429` e `5xx` NÃO são definitivos: o front reenvia com a MESMA chave.
  Replay é checado ANTES do limite de frequência; `429` nunca é gravado. (RF13)
- Abrir/fechar leilões: worker em processo separado (`manage.py run_auction_worker`,
  loop de 1s) que lê o BANCO com `select_for_update(skip_locked=True)`. Nada de
  timers em memória. Sobrevive a reinício; fechar 2x não duplica; o worker fecha com
  `now >= ends_at` (complemento exato da regra do lance). (RF17, RF18)
- Prorrogação: se restam < 2 min no lance aceito,
  `ends_at = min(now + 2 min, original_ends_at + 30 min)`. Guardar `original_ends_at`. (RF15)
- Lance mínimo é calculado SÓ no servidor, função pura do estado do leilão. Antes do 1º
  lance, `min_next_bid_cents = start_price_cents`. (RF14)
- Comitente nunca dá lance no próprio leilão (`IS_SELLER`), mas PODE entrar na sala.
  Listagem pública; sala exige login; o detalhe público não mostra líder nem lances. (RF04)
- Líder exibido sem expor o nome completo (`leader_label`). (RF09)
- Limites de criação (textos, fotos, duração, antecedência) vêm de config/env. (RF06)
- Auth: sessão Django (cookie HttpOnly) + CSRF (`X-CSRFToken`), 1 h deslizante. (RF02)
- Dados de demonstração (RNF04): `manage.py seed_demo` cria ≥ 1 comitente, 3 compradores
  e leilões em estados diferentes (com ≥ 3 fotos cada e alguns de duração curta).

## Convenções
- Erros: `{ "code": "BID_TOO_LOW", "message": "...", ...extras }` (ver contrato)
- IDs: UUID. Datas na API: ISO 8601 com `Z`. Campos da API em `snake_case`.
- Segredos só em `.env` (nunca commitar).

## Comandos (dev local)
- Infra: `docker compose up -d db redis`
- Backend: `cd backend && python manage.py runserver 8000` (ASGI/Channels)
- Worker: `cd backend && python manage.py run_auction_worker`
- Seed: `cd backend && python manage.py seed_demo`
- Front: `cd frontend && npm run dev` (proxy de `/api`, `/ws` e `/media` para localhost:8000)
- Tudo (VM): `docker compose up -d --build`

## Requisitos completos
O PDF `docs/Requisitos_Leilao_Hackathon.pdf` tem a lista oficial (RF01–RF32, RNF01–RNF04),
com UMA correção da organização: as fotos ficam no disco local da VM (RF07).
Ordem de entrega: Núcleo inteiro → Nível 2 → Bônus. Primeiro o fluxo completo
(criar, abrir, dar lance, fechar), mesmo feio; depois refinar.
