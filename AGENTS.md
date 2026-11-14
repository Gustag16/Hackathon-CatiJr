# Leilão Online — Time Katchau (Hackathon CATI Cloud Labs)

Plataforma web de leilão online em tempo real, hospedada em uma VM. Simulação:
nenhuma transação é real. Este arquivo é a fonte de verdade para humanos E para
qualquer assistente de IA (Claude, Gemini etc.). Leia inteiro antes de editar.

## Regras de trabalho (obrigatórias)
1. Leia `docs/contract.md` antes de tocar em qualquer endpoint ou evento WebSocket.
2. Cada pessoa é dona de uma pasta. NÃO edite a pasta de outro membro; peça a ele.
   - `backend/`  → Danilo (modelos, máquina de estados, motor de lances, worker)
   - `frontend/` → Amadeu (todas as telas)
   - `deploy/` + docker-compose + consumer WebSocket/presença → Bortoleto
3. Mudou o contrato? Avise no grupo ANTES de mexer no código.
4. Registre decisões em `docs/decisions.md` (1–2 frases de justificativa). A banca cobra.
5. Commits pequenos, branch por pessoa, `git pull origin main` de hora em hora.
6. Código gerado por IA só entra se alguém do time consegue explicá-lo. A banca
   escolhe quem responde.

## Stack
- Backend: Python + Django + Django REST Framework + Django Channels (ASGI), PostgreSQL 16
- Channel layer: Redis (fan-out do WebSocket; viabiliza várias instâncias — bônus)
- Tempo real: WebSocket (Channels). Lances são POST HTTP; o WS só transmite estado.
- Frontend: React + Vite + TypeScript + Tailwind (SPA estática)
- Proxy: Caddy na porta 8080 da VM (front em `/`, API em `/api`, WS em `/ws`)
- Fotos: serviço de armazenamento em nuvem da organização (NUNCA no banco nem no disco
  da VM). Tipo do serviço: a confirmar com a organização.
- Tudo sobe com `docker compose up -d --build`

## Restrições de infraestrutura
- A VM só expõe UMA porta pública, repassada para a 8080 dentro da VM.
- O front DEVE escutar na 8080 (via Caddy). Mesma origem: sem CORS.
- Todos os fluxos devem funcionar pela interface web (sem Postman/console).
- O Django admin NÃO pode ficar acessível em produção (RF03: não existe administrador).

## Estados do leilão (RN01) — 5 estados, 5 transições
`scheduled` → `running` (chegou o início)
`scheduled` → `cancelled` (comitente, antes do início)
`running` → `cancelled` (comitente, SÓ se não houver lances)
`running` → `sold` (fim, com lances)
`running` → `ended_no_bids` (fim, sem lances)
`sold`, `ended_no_bids` e `cancelled` são finais. Com lances, só termina `sold`.
Toda transição passa por UMA função central; nenhum outro código altera `status`.

## Invariantes que NÃO podem ser violadas (a banca testa)
- Dinheiro: inteiro em CENTAVOS (`*_cents`) no banco e na API. Nunca float. (RF19)
- Tempo: UTC no banco (`USE_TZ=True`); o horário válido é SEMPRE o do servidor
  (`timezone.now()`). O contador do navegador é só visual. (RF16, RF19)
- Lance: `transaction.atomic()` + `select_for_update()` na linha do leilão, validando
  as 4 condições do RF10 NO MOMENTO do processamento (lance mínimo vigente agora, não
  o da tela): sessão válida e na sala; leilão `running` e antes do fim; autor não é o
  comitente nem o líder; valor ≥ lance mínimo. (RF10, RF11)
- Broadcast SÓ DEPOIS do commit: use `transaction.on_commit(...)` ao chamar o
  `group_send` do Channels. A sala nunca vê estado não gravado. (RF11)
- Idempotência: cada tentativa de lance leva `Idempotency-Key` (UUID gerado no
  navegador). Tabela com UNIQUE(usuário, chave) guarda status + corpo, INCLUSIVE
  recusas. Mesma chave → devolve o resultado ORIGINAL. Mesma chave com valor
  diferente → erro `IDEMPOTENCY_KEY_MISMATCH`. O front gera chave NOVA a cada novo
  lance/valor; só reaproveita a chave ao reenviar o MESMO envio. (RF12)
- Abrir/fechar leilões: worker em processo separado (`manage.py run_auction_worker`,
  loop de 1s) que lê o BANCO com `select_for_update(skip_locked=True)`. Nada de
  timers em memória. Sobrevive a reinício; fechar 2x não duplica; nunca há lance
  após o fechamento nem fechamento no meio de um lance (mesma trava). (RF17, RF18)
- Prorrogação: lance com menos de 2 min restantes leva o término para 2 min depois
  do lance, no máximo 30 min acumulados sobre o término ORIGINAL (guardar
  `original_ends_at`). (RF15)
- Lance mínimo é calculado SÓ no servidor, função pura do estado do leilão. (RF14)
- Comitente nunca dá lance no próprio leilão. Listagem pública; sala exige login. (RF04)
- Líder exibido sem expor o nome completo (`leader_label`). (RF09)
- Limites de criação (textos, fotos, duração, antecedência) vêm de config/env. (RF06)
- Auth: sessão Django (cookie HttpOnly) + CSRF (`X-CSRFToken`). (RF02)

## Convenções
- Erros: `{ "code": "BID_TOO_LOW", "message": "...", ...extras }` (ver contrato)
- IDs: UUID. Datas na API: ISO 8601 com `Z`. Campos da API em `snake_case`.
- Segredos só em `.env` (nunca commitar).

## Comandos (dev local)
- Infra: `docker compose up -d db redis`
- Backend: `cd backend && python manage.py runserver 8000` (ASGI/Channels)
- Worker: `cd backend && python manage.py run_auction_worker`
- Front: `cd frontend && npm run dev` (proxy de `/api` e `/ws` para localhost:8000)
- Tudo (VM): `docker compose up -d --build`

## Requisitos completos
O PDF "Requisitos_Leilao_Hackathon" tem a lista oficial (RF01–RF32, RNF01–RNF04).
Ordem de entrega: Núcleo inteiro → Nível 2 → Bônus. Primeiro o fluxo completo
(criar, abrir, dar lance, fechar), mesmo feio; depois refinar.
