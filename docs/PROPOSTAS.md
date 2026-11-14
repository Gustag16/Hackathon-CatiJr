# Propostas para o time votar

Coisas que eu (Claude, na branch `danilo/fable-organiza`) achei mas que **não são minhas para mudar**:
contrato, `AGENTS.md`, `frontend/`, `deploy/` e `docker-compose.yml`. Cada item: o quê, por quê,
custo, quem é afetado. Marque ✅/❌ e registre as aceitas na tabela de decisões do `README.md`.

## Contrato (`docs/contract.md`)

### 1. Documentar `GET /api/health`
- **O quê**: `200 {status:"ok", db:true, redis:true, server_time}` ou `503 {status:"degraded", ...}`. Sem login.
- **Por quê**: healthcheck do compose, `make doctor` e diagnóstico na demo. Já existe no backend
  (`backend/config/health.py`); só falta constar no contrato.
- **Custo**: uma linha na seção 3. **Afeta**: Bortoleto (healthcheck); ninguém mais.

### 2. Combinar a ponte backend → consumer do WebSocket
- **O quê**: o backend publica no grupo `auction_<uuid>` a mensagem interna
  `{"type": "room.event", "message": <evento do contrato, seção 5>}`. O consumer entra nesse grupo
  e implementa `async def room_event(self, event): await self.send_json(event["message"])`.
  Está em `backend/auctions/services/broadcast.py`.
- **Por quê**: o contrato define o que o navegador recebe, mas não como o lance (Danilo) entrega o
  evento ao consumer (Bortoleto). Sem combinar, cada um inventa um nome.
- **Custo**: 5 linhas no consumer. **Afeta**: Bortoleto, Danilo.

### 3. Aceitar frações de segundo nas datas
- **O quê**: o DRF serializa `2026-11-14T19:02:27.582992Z`; o exemplo do contrato mostra sem fração.
  Proposta: o contrato dizer "pode trazer fração de segundo".
- **Por quê**: `new Date(...)` lê os dois formatos; truncar no servidor é trabalho sem ganho, e a
  fração ajuda a ordenar lances do mesmo segundo.
- **Custo**: zero se o front usa `new Date()`. **Afeta**: Amadeu (não comparar datas como texto).

### 4. `outbid` do Nível 2 sem expor quem é quem
- **O quê**: quando chegar a hora do RF26, o evento "só para quem foi superado" exige que o consumer
  saiba o usuário do líder anterior. Sugestão: o backend publica `previous_leader_number` em
  `bid_accepted` e o front compara com `you.participant_number` (sem evento novo).
- **Por quê**: mantém a regra do D4 (a API nunca expõe id de usuário) e evita grupo por usuário.
- **Custo**: um campo a mais em `bid_accepted`. **Afeta**: os três, só no Nível 2.

## `docker-compose.yml` e `deploy/` (Bortoleto)

### 5. Serviços que faltam no compose
- **O quê**: `backend` (build `./backend`, comando padrão do Dockerfile), `worker` (mesma imagem,
  `command: python manage.py run_auction_worker`), `caddy` (8080; front, `/api`, `/ws`, `/media`).
  Volume `media` montado em `/srv/media` no backend (rw) e no Caddy (ro). `depends_on` com
  `condition: service_healthy` para `db` e `redis`. Healthcheck do backend em `/api/health`.
- **Por quê**: hoje `docker compose up -d --build` só sobe banco e Redis; o RNF03 e a demo de
  reinício dependem disso. Quanto antes subir na VM, melhor (dica "Publique cedo" do PDF).
- **Custo**: ~40 linhas de YAML + Caddyfile. **Afeta**: Bortoleto; Danilo testa o Dockerfile.

### 6. Variáveis que mudam dentro do compose
- **O quê**: no compose, `DATABASE_URL` e `REDIS_URL` precisam apontar para `db` e `redis`, não
  `localhost` (o `.env.example` é de dev local). Sugestão: `environment:` no serviço sobrescrevendo
  só essas duas e `MEDIA_ROOT=/srv/media`.
- **Por quê**: com `localhost` o backend em container não acha o banco.
- **Custo**: 3 linhas. **Afeta**: Bortoleto.

### 7. Migrações com mais de uma instância (bônus)
- **O quê**: o `CMD` do Dockerfile roda `migrate` antes do servidor. Com 2 réplicas do backend, as
  duas migram ao mesmo tempo. Se formos atrás do bônus, mover o `migrate` para um serviço de uma
  execução só (`restart: "no"`) do qual backend e worker dependem.
- **Por quê**: evita corrida de migração e o worker começar antes de as tabelas existirem.
- **Custo**: 8 linhas no compose. **Afeta**: Bortoleto, Danilo.

### 8. Worker com parada limpa
- **O quê**: `restart: unless-stopped` e `stop_grace_period: 10s` no worker.
- **Por quê**: no cenário de reinício da banca, o worker deve terminar a passada atual e voltar sozinho.
- **Custo**: 2 linhas. **Afeta**: Bortoleto.

## `frontend/` (Amadeu)

### 9. Proxy de desenvolvimento no Vite
- **O quê**: `frontend/vite.config.ts` ainda não tem o proxy que o AGENTS.md descreve
  (`/api`, `/ws` com `ws: true` e `/media` → `http://localhost:8000`).
- **Por quê**: sem ele, em dev o front fala com outra origem e o cookie de sessão/CSRF não funciona.
- **Custo**: 8 linhas. **Afeta**: Amadeu.

### 10. Um único módulo de API no front
- **O quê**: uma função `api()` que põe `X-CSRFToken`, trata `401` (volta ao login guardando o lance
  pendente e a MESMA `Idempotency-Key`) e converte `*_cents` para exibição só na hora de mostrar.
- **Por quê**: as regras de chave do contrato (seção 4) são fáceis de errar se cada tela fizer `fetch`.
- **Custo**: ~40 linhas, uma vez. **Afeta**: Amadeu.

## `AGENTS.md` / raiz

### 11. Apontar os comandos para o Makefile
- **O quê**: na seção "Comandos", trocar a lista por `make db | migrate | backend | worker | seed |
  test | test-todo | lint | doctor | smoke | stress` (os comandos de hoje continuam valendo).
- **Por quê**: um jeito só de rodar, para humanos e assistentes de IA.
- **Custo**: editar 8 linhas. **Afeta**: os três.

### 12. Regra de relógio para o código do backend
- **O quê**: acrescentar às invariantes: "serviços leem a hora por `auctions.services.clock.now()`,
  chamado DEPOIS de obter a trava".
- **Por quê**: se a hora for lida antes do `select_for_update`, um lance que esperou na fila pode
  ser aceito depois do término. E os testes controlam o tempo trocando essa função.
- **Custo**: uma linha. **Afeta**: Danilo.

### 13. Usuários do GitHub no CODEOWNERS
- **O quê**: preencher `@amadeu-TODO` e `@bortoleto-TODO` em `.github/CODEOWNERS`.
- **Por quê**: enquanto forem inválidos, o GitHub ignora essas linhas.
- **Custo**: 1 min. **Afeta**: Amadeu, Bortoleto.
