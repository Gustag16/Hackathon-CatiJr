# Decisões da equipe (vão para o README e para o pitch)

Cada requisito marcado "Decisão da equipe" precisa de 1–2 frases de justificativa.
As 2–3 mais difíceis aparecem no pitch: o que foi considerado e o que cada escolha custou.

| Req. | Decisão | Justificativa / custo |
|---|---|---|
| RNF01 | Arquitetura na VM: Caddy + Django/Channels (ASGI) + worker + Postgres + Redis via compose | |
| RF09 | Tempo real: WebSocket (Django Channels, Redis como channel layer) | |
| RF09 | Como identificar o líder sem expor o nome (D4): ? | |
| RF02 | Sessão: duração e renovação (D2): ? | |
| RF05/RF06 | Categorias e limites (D6): ? | |
| RF07 | Tipos e tamanhos de foto aceitos: ? | |
| RF10 | "Estar na sala" (D3): ? | |
| RF11 | Controle de concorrência: select_for_update na linha do leilão | |
| RF12 | Idempotência: Idempotency-Key + tabela UNIQUE(usuário, chave) guardando também recusas | |
| RF14 | Regra do lance mínimo (tabela de referência do PDF?): ? | |
| RF15 | Prorrogação: 2 min / máx. 30 min acumulados (referência do PDF)? | |
| RF17/18 | Abertura/fechamento: worker lendo o banco (não timers em memória) | |
| RF19 | Dinheiro em centavos inteiros (D1): ? | |
| RF20 | O que mostrar na listagem, ordem e paginação: ? | |
