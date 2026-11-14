# Pitch — esqueleto

O PDF (10.2) pede três respostas. Nas perguntas, **a banca escolhe quem responde**: os três
precisam saber explicar cada bloco. Frases entre colchetes são para preencher.

## 1. Qual a arquitetura na VM e por quê (≈1 min)

Mostrar o primeiro diagrama de `docs/architecture.md`.

- Uma porta pública → Caddy na frente de tudo; mesma origem, sem CORS.
- Monolito Django (REST + WebSocket no mesmo processo ASGI) + worker separado + PostgreSQL + Redis,
  tudo em `docker compose`. Em 8 horas, menos peças = menos pontos de falha.
- O banco é a única fonte de verdade; Redis só espalha mensagens; o worker não tem memória.
- [o que sobe com um comando / tempo para recriar do zero: ___ min]

## 2. As 2–3 decisões mais difíceis: o que consideramos e o que custou

### a) Concorrência de lances: trava de linha no banco (RF11)
- **Consideramos**: fila por leilão em memória/Redis; isolamento serializável com retentativa;
  `select_for_update` na linha do leilão.
- **Escolhemos** a trava de linha: correta com várias instâncias do backend, simples de explicar,
  e a MESMA trava serve para lance, cancelamento e fechamento.
- **Custou**: lances do mesmo leilão são processados um por vez. [medida do stress: ___ lances/s]

### b) Lance por HTTP, WebSocket só para transmitir (RF09, RF12)
- **Consideramos**: lance pelo próprio WebSocket.
- **Escolhemos** POST: resposta com motivo da recusa, idempotência por `Idempotency-Key` e sessão
  expirada tratadas pelo caminho normal do HTTP. A sala só recebe estado **depois do commit**.
- **Custou**: dois canais para manter coerentes (por isso `snapshot` ao reconectar) e a regra de
  quais respostas são definitivas (201 e 409 gravam; 401/429/5xx reenviam com a mesma chave).

### c) Tempo: worker lendo o banco, regra `now < ends_at` (RF16–RF18)
- **Consideramos**: timer em memória por leilão; agendador externo (cron/Celery beat).
- **Escolhemos** um loop de 1 s que pergunta ao banco o que está atrasado, com `skip_locked`.
- **Custou**: até 1 s de atraso para o status mudar. Não vira bug porque o lance é recusado por
  `now >= ends_at` mesmo antes de o worker passar.

Reserva (se perguntarem): "estar na sala" = sessão válida (D3); rótulo `Dan*** #3` (D4); fotos no
disco da VM por orientação da organização (D5); dinheiro em centavos inteiros (D1).

## 3. O que ficou de fora e por quê

- [Nível 2 não entregue: ___] — priorizamos o Núcleo inteiro funcionando de ponta a ponta.
- [Bônus de crédito/pontuação (RF29–RF32)] — muda o cadastro e o lance; risco alto no fim do dia.
- [HTTPS com domínio / banco gerenciado / deploy automático] — [motivo].
- Limitações conhecidas que assumimos: [listagem atualiza a cada 30 s, não em tempo real], [___].

## Perguntas prováveis (treinar com os três)

1. O que acontece se dois lances iguais chegam no mesmo milissegundo? (mostrar a trava e o teste)
2. E se o servidor cair faltando 10 s para o fim? (worker lê o banco; `now >= ends_at` fecha ao voltar)
3. Por que o cliente gera a chave de idempotência e não o servidor?
4. O que impede o navegador de mentir sobre a hora? (o servidor nunca recebe hora do cliente)
5. Como vocês sabem que funciona? (`make test`, `scripts/stress_bids.py`, `docs/demo-script.md`)
6. Qual parte a IA escreveu e como vocês validaram? (testes escritos antes; cada linha revisada)
7. Por que centavos inteiros e não `Decimal`?
8. O que muda com duas instâncias do backend? (nada no lance: a trava é do banco; WS via Redis)
