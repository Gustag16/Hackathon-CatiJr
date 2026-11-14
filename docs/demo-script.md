# Roteiro da demo

A banca executa cenários ela mesma no sistema publicado, "inclusive lances simultâneos, horário de
término e reinício do sistema" (PDF, 10.3), e pode pedir que qualquer um conduza. Ensaie TODOS os
cenários pela interface (RNF02: sem Postman nem console).

## Antes de a banca chegar (10 min)

- [ ] `BASE=http://localhost:8080 bash scripts/doctor.sh` na VM: tudo verde
- [ ] `python3 scripts/smoke_test.py --base http://<vm>:<porta>`: tudo verde
- [ ] `seed_demo` rodado; contas de demonstração anotadas no README
- [ ] Limites curtos no `.env` da VM (`MIN_START_DELAY_SECONDS=30`, `MIN_DURATION_SECONDS=60`)
- [ ] 3 navegadores/perfis logados: comitente, comprador A, comprador B (+ 1 janela anônima)
- [ ] Um leilão "longo" em andamento com lances e um agendado, para nunca faltar o que mostrar
- [ ] Terminal aberto na VM em `docker compose logs -f worker`

## Cenários

| # | Cenário (requisito) | Passos | O que tem que aparecer |
|---|---|---|---|
| 1 | Visitante (RF04, RF20) | Janela anônima: abrir a listagem; clicar num leilão; tentar entrar na sala | Listagem e detalhe abrem; a sala pede login; detalhe não mostra líder |
| 2 | Cadastro e login (RF01) | Cadastrar; tentar o mesmo e-mail em maiúsculas | 2ª tentativa: "e-mail já cadastrado" |
| 3 | Criar leilão curto (RF05–RF07) | Comitente: 3 fotos, início em 1 min, duração 3 min; tentar com 2 fotos | Validação recusa 2 fotos; com 3 nasce "Agendado" |
| 4 | Abre sozinho (RF17) | Todos na sala do leilão agendado; ninguém toca em nada | No horário vira "Em andamento" em todas as telas, sem recarregar |
| 5 | Comitente não dá lance (RF04) | Comitente tenta dar lance no próprio leilão | Recusa com motivo |
| 6 | Lance e tempo real (RF09, RF10) | A dá lance; B olha a tela | Preço, mínimo, líder (`Xxx*** #n`), total e histórico mudam na hora nas 3 telas |
| 7 | Líder não cobre a si mesmo (RF10) | A tenta outro lance | Recusa "você já é o líder" |
| 8 | Mínimo vigente (RF10.4) | B digita valor abaixo do mínimo | Recusa mostra o mínimo atual |
| 9 | **Lances simultâneos (RF11)** | A e B digitam o MESMO valor e clicam juntos (contagem 3-2-1) | Um aceito, o outro recusado com o novo mínimo; nunca dois lances iguais |
| 10 | Clique duplo (RF12) | Clicar duas vezes rápido em "Dar lance" | Um lance só no histórico |
| 11 | **Prorrogação (RF15)** | Dar lance com menos de 2 min no relógio | O cronômetro de todos pula para 2:00 |
| 12 | **Horário de término (RF16, RF17)** | Esperar zerar; tentar lance no último instante | Fecha sozinho: "Vendido" com vencedor e valor; lance tardio recusado |
| 13 | Sem lances (RN01) | Leilão curto sem ninguém dar lance | "Encerrado sem lances" |
| 14 | Cancelamento (RF08) | Cancelar um agendado; cancelar um em andamento sem lances; tentar cancelar um com lances | Dois primeiros viram "Cancelado" (continuam visíveis pelo link); o terceiro é recusado |
| 15 | **Reinício (RF18)** | Criar leilão que fecha em ~2 min, dar lance; `docker compose restart backend worker`; esperar | Sala reconecta com o estado certo; fecha no horário como "Vendido"; lance não se perdeu |
| 16 | Reinício longo (RF18) | `docker compose stop worker`; esperar passar o início de um e o término de outro; `start worker` | Em segundos: o agendado abre, o vencido fecha, uma vez só |
| 17 | Fuso (RF19) | Mudar o fuso do sistema/navegador de um dos computadores | Mesmos instantes, mostrados no fuso de cada um |
| 18 | Sessão expirada (RF02) | (com `SESSION_COOKIE_AGE_SECONDS` curto) esperar expirar e tentar lance | Pede login; depois do login o lance segue |

Cenários em **negrito** são os que o PDF cita nominalmente.

## Carta na manga (se sobrar tempo)

`python3 scripts/stress_bids.py --base http://<vm>:<porta>` com a sala aberta no telão: 50 lances
ao mesmo tempo, a sala anda sem travar e o script imprime as invariantes conferidas (bônus "teste de
carga", PDF 7.2).

## Se algo der errado ao vivo

| Problema | Ação |
|---|---|
| Leilão não abre/fecha | `docker compose logs --tail=20 worker`; `docker compose restart worker` (é seguro: lê do banco) |
| Sala parada | Recarregar a página (o `snapshot` traz o estado); conferir `curl localhost:8080/api/health` |
| Tudo fora | `docker compose up -d`; os dados estão nos volumes |
