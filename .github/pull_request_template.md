## O que muda
<!-- 1 a 3 linhas -->

## Checklist (AGENTS.md)
- [ ] Só mexi na minha pasta (ou combinei com o dono)
- [ ] Não mudei `docs/contract.md` sem avisar no grupo
- [ ] Dinheiro em centavos inteiros (`*_cents`), nenhum float
- [ ] Horário vem do servidor (`timezone.now()`), nunca do navegador
- [ ] Nenhum código novo altera `status` fora da função central
- [ ] Broadcast só em `transaction.on_commit`
- [ ] Sem segredo no diff (`.env`, chaves)
- [ ] `make test` e `make lint` passam
- [ ] Decisão nova registrada na tabela do `README.md`
- [ ] Eu consigo explicar cada linha deste PR para a banca

## Como testar
<!-- comandos ou passos na tela -->
