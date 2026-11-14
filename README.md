# Katchau — Leilão Online

Hackathon CATI Cloud Labs. Time: Danilo, Amadeu, Bortoleto.

## Endereço do sistema publicado
(preencher: http://200.18.99.113:<porta-web>)

## Como recriar o ambiente do zero (RNF03)
Passo a passo completo (dev e VM) em [docs/runbook.md](docs/runbook.md). Resumo em dev:

```bash
cp .env.example .env && make db && make migrate
make backend    # terminal 1: API em http://localhost:8000
make worker     # terminal 2: abre e fecha leilões
make doctor     # confere o ambiente
```

Outros documentos: [arquitetura](docs/architecture.md) · [contrato da API](docs/contract.md) ·
[roteiro da demo](docs/demo-script.md) · [pitch](docs/pitch.md) · [propostas em votação](docs/PROPOSTAS.md)

## Contas de demonstração (RNF04)
(preencher: 1+ comitente, 3 compradores, leilões em estados diferentes)

## Decisões da equipe

Cada decisão do PDF ("Decisão da equipe"), com 1–2 frases de justificativa. Status: **C** confirmada,
**P** proposta (a validar no grupo), **?** a definir.

| Req. | Decisão | Justificativa e custo | St. |
|---|---|---|---|
| RNF01 | Caddy (8080) → Django ASGI (REST + Channels) + worker + PostgreSQL + Redis, tudo em docker compose | Só há uma porta pública, então um proxy na frente; um monolito reduz pontos de falha em 8 h. Custo: Redis a mais na VM. | P |
| RF09 | Tempo real por WebSocket (Django Channels, Redis como channel layer); lance por POST | O POST devolve o motivo da recusa e facilita a idempotência; o WS só transmite estado. Custo: dois canais a manter consistentes (broadcast pós-commit e snapshot ao reconectar). | P |
| RF09 | Líder mostrado como nome mascarado + nº do participante no leilão (ex.: `Dan*** #3`) (D4) | Não expõe o nome completo e quem deu o lance se reconhece pelo número. A API não expõe o id do líder. Custo: tabela de participantes por leilão, numerada sob a mesma trava do lance. | C |
| RF02 | Sessão Django (cookie) + CSRF, 1 h deslizante | Renova com o uso e o WebSocket reaproveita o cookie. Custo: tratar o CSRF no front. | P |
| RF05/06 | Limites: nome ≤ 100, descrição ≤ 2000, 3–8 fotos, duração ≥ 60 s, início ≥ 30 s à frente; categorias: Automóveis, Móveis, Eletrônicos, Arte, Hobbies e música, Colecionáveis, Outros (D6) | Valores vêm de config, fáceis de encurtar para a demo (início mínimo de 30 s para caber "abre em 1 min"). Categorias fixas no backend, com "Outros" para nenhum item ficar sem opção. | P |
| RF07 | Fotos no disco local da VM (adendo da organização), volume Docker servido pelo Caddy; jpeg/png/webp até 5 MB | Segue a correção da organização; só o caminho vai ao banco. Custo: sem CDN, o disco da VM é o limite. | C |
| RF10 | "Estar na sala" = sessão válida (a sala exige login), sem presença por WebSocket | Funciona com várias instâncias e sem presença fantasma. Custo: leitura mais fraca da condição do RF10. | P |
| RF11 | `select_for_update` na linha do leilão dentro de transação | Simples e correto com um banco só. Custo: lances do mesmo leilão serializam. | P |
| RF12 | `Idempotency-Key` + tabela UNIQUE(usuário, chave) que guarda também as recusas | Reenvio devolve o resultado original sem 2º lance. Custo: tabela extra e regra clara de quais respostas são definitivas. | P |
| RF14 | Lance mínimo pela tabela de referência do PDF, em centavos | Regra pronta, função pura do estado do leilão. | P |
| RF15 | Prorrogação: 2 min, no máximo 30 min acumulados (referência do PDF) | Evita lance de último segundo sem deixar o leilão infinito. | P |
| RF17/18 | Worker em processo separado lendo o banco a cada 1 s | Sobrevive a reinício; timers em memória se perdem. Custo: até 1 s de atraso, coberto pela regra `now < ends_at` no lance. | P |
| RF19 | Dinheiro em centavos inteiros, UTC no banco | Sem erro de arredondamento. | C |
| RF20 | Grade de cartões (foto, status, preço, nº de lances, tempo), abas Em andamento/Agendados/Todos, ordenada por término (andamento) e início (agendados), 12 por página com paginação numerada | Quem termina primeiro é o mais urgente para o comprador; a paginação evita carregar tudo com muitos leilões. Custo: atualiza a cada 30 s, não em tempo real. | P |
