# Katchau — Leilão Online

Hackathon CATI Cloud Labs. Time: Danilo, Amadeu, Bortoleto.

## Endereço do sistema publicado
(preencher: http://200.18.99.113:<porta-web>)

## Como recriar o ambiente do zero (RNF03)
Fluxo da VM (Ubuntu 24.04, 1 vCPU, ~1 GB de RAM). Desenvolvimento local e problemas comuns:
[docs/runbook.md](docs/runbook.md).

**1. Pré-requisitos:** Docker com o plugin Compose e 2 GB de swap (sem swap o build do front
estoura a memória).

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

**2. Código e configuração:**

```bash
git clone https://github.com/Gustag16/Hackathon-CatiJr.git
cd Hackathon-CatiJr
cp .env.example .env
openssl rand -hex 32   # valor para DJANGO_SECRET_KEY
```

Edite no `.env` (os demais valores podem ficar como estão; o `.env` nunca é commitado):

```
DJANGO_SECRET_KEY=<saída do openssl>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=<IP da VM>,backend,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://<IP da VM>:<porta pública>
```

**3. Build e subida** (uma imagem por vez, para caber na memória):

```bash
docker compose build backend
docker compose build caddy
docker compose up -d
```

O backend aplica as migrações ao subir. Banco e fotos ficam em volumes Docker e sobrevivem a
reinício e a `docker compose down`.

**4. Dados de demonstração:**

```bash
docker compose exec backend python manage.py seed_demo
```

**5. Verificação:**

```bash
curl localhost:8080/api/health
```

Depois abra `http://<IP da VM>:<porta pública>` no navegador.

**Atualizar:** `git pull` e refaça o build só do que mudou (`docker compose build backend` para
`backend/`; `docker compose build caddy` para `frontend/` ou `deploy/`), depois `docker compose up -d`.

Outros documentos: [arquitetura](docs/architecture.md) · [contrato da API](docs/contract.md) ·
[roteiro da demo](docs/demo-script.md) · [pitch](docs/pitch.md) · [propostas em votação](docs/PROPOSTAS.md)

## Contas de demonstração (RNF04)
Criadas pelo `seed_demo` (passo 4). Senha de todas: `leilao-demo-2026`.

| Papel | E-mail | Nome |
|---|---|---|
| Comitente (dono dos ~100 leilões) | `comitente@demo.test` | Carlos Comitente |
| Comprador | `ana@demo.test` | Ana Compradora |
| Comprador | `bruno@demo.test` | Bruno Comprador |
| Comprador | `carla@demo.test` | Carla Compradora |

Leilões: 25 em andamento (5 fecham em até 10 min), 40 agendados (6 abrem em até 5 min e duram 3),
18 vendidos, 9 encerrados sem lances, 8 cancelados; 3 fotos cada. Rodar de novo não duplica;
`docker compose exec backend python manage.py seed_demo --reset` recria com horários novos (usar
pouco antes da demo).

## Decisões da equipe

Cada decisão do PDF ("Decisão da equipe"), com 1–2 frases de justificativa. Status: **C** confirmada,
**P** proposta (a validar no grupo), **?** a definir.

| Req. | Decisão | Justificativa e custo | St. |
|---|---|---|---|
| RNF01 | Caddy (8080) → Django ASGI (REST + Channels) + worker + PostgreSQL + Redis, tudo em docker compose | Só há uma porta pública, então um proxy na frente; um monolito reduz pontos de falha em 8 h. Custo: Redis a mais na VM. || C |
| RF09 | Tempo real por WebSocket (Django Channels, Redis como channel layer); lance por POST | O POST devolve o motivo da recusa e facilita a idempotência; o WS só transmite estado. Custo: dois canais a manter consistentes (broadcast pós-commit e snapshot ao reconectar). || C |
| RF09 | Líder mostrado como nome mascarado + nº do participante no leilão (ex.: `Dan*** #3`) (D4) | Não expõe o nome completo e quem deu o lance se reconhece pelo número. A API não expõe o id do líder. Custo: tabela de participantes por leilão, numerada sob a mesma trava do lance. | C |
| RF02 | Sessão Django (cookie) + CSRF, 1 h deslizante | Renova com o uso e o WebSocket reaproveita o cookie. Custo: tratar o CSRF no front. || C |
| RF05/06 | Limites: nome ≤ 100, descrição ≤ 2000, 3–8 fotos, duração ≥ 60 s, início ≥ 30 s à frente; categorias: Automóveis, Móveis, Eletrônicos, Arte, Hobbies e música, Colecionáveis, Outros (D6) | Valores vêm de config, fáceis de encurtar para a demo (início mínimo de 30 s para caber "abre em 1 min"). Categorias fixas no backend, com "Outros" para nenhum item ficar sem opção. || C |
| RF07 | Fotos no disco local da VM (adendo da organização), volume Docker servido pelo Caddy; jpeg/png/webp até 5 MB | Segue a correção da organização; só o caminho vai ao banco. Custo: sem CDN, o disco da VM é o limite. | C |
| RF10 | "Estar na sala" = sessão válida (a sala exige login), sem presença por WebSocket | Funciona com várias instâncias e sem presença fantasma. Custo: leitura mais fraca da condição do RF10. || C |
| RF11 | `select_for_update` na linha do leilão dentro de transação | Simples e correto com um banco só. Custo: lances do mesmo leilão serializam. || C |
| RF12 | `Idempotency-Key` + tabela UNIQUE(usuário, chave) que guarda também as recusas | Reenvio devolve o resultado original sem 2º lance. Custo: tabela extra e regra clara de quais respostas são definitivas. || C |
| RF14 | Lance mínimo pela tabela de referência do PDF, em centavos | Regra pronta, função pura do estado do leilão. || C |
| RF15 | Prorrogação: 2 min, no máximo 30 min acumulados (referência do PDF) | Evita lance de último segundo sem deixar o leilão infinito. || C |
| RF17/18 | Worker em processo separado lendo o banco a cada 1 s | Sobrevive a reinício; timers em memória se perdem. Custo: até 1 s de atraso, coberto pela regra `now < ends_at` no lance. || C |
| RF19 | Dinheiro em centavos inteiros, UTC no banco | Sem erro de arredondamento. | C |
| RF20 | Grade de cartões (foto, status, preço, nº de lances, tempo), abas Em andamento/Agendados/Todos, ordenada por término (andamento) e início (agendados), 12 por página com paginação numerada | Quem termina primeiro é o mais urgente para o comprador; a paginação evita carregar tudo com muitos leilões. Custo: atualiza a cada 30 s, não em tempo real. || C |
