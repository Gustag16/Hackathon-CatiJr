# Runbook — recriar o ambiente do zero (RNF03)

## Máquina de desenvolvimento

Pré-requisitos: Docker com Compose, Python 3.12+, Node 20+, `make`.

```bash
git clone <repo> && cd Hackathon-CatiJr
cp .env.example .env          # ajuste se precisar; nunca commite
make db                       # PostgreSQL + Redis (espera ficarem saudáveis)
make migrate                  # cria o venv em backend/.venv e aplica as migrações
make backend                  # API em http://localhost:8000 (terminal 1)
make worker                   # abre/fecha leilões (terminal 2)
cd frontend && npm install && npm run dev   # front em http://localhost:5173 (terminal 3)
make seed                     # dados de demonstração (RNF04)
make doctor                   # confere tudo de uma vez
```

`make help` lista as tarefas. `make test` tem que estar verde; `make test-todo` é a lista do que
falta nas garantias de lance e worker.

Problemas conhecidos:

| Sintoma | Causa e saída |
|---|---|
| `permission denied ... docker.sock` | usuário fora do grupo `docker` nesta sessão: `newgrp docker` ou relogar |
| `pip` falha no `autobahn` (Python 3.15) | extensão nativa não compila; o `make venv` já usa `AUTOBAHN_USE_NVX=0` |
| `make doctor` acusa chaves faltando no `.env` | o `.env.example` ganhou chaves novas; copie as que faltam |
| CSRF 403 em POST | a origem do navegador não está em `DJANGO_CSRF_TRUSTED_ORIGINS` |
| WebSocket fecha na hora (403) | o host da página não está em `DJANGO_ALLOWED_HOSTS` |

## VM (produção da demo)

> Depende do `docker-compose.yml` completo (backend, worker, caddy), que é do Bortoleto.
> Ver `docs/PROPOSTAS.md`, item 3. Os passos abaixo são o alvo.

```bash
git clone <repo> && cd Hackathon-CatiJr
cp .env.example .env
# Editar o .env da VM:
#   DJANGO_DEBUG=0
#   DJANGO_SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(50))">
#   DJANGO_ALLOWED_HOSTS=200.18.99.113
#   DJANGO_CSRF_TRUSTED_ORIGINS=http://200.18.99.113:<porta-web>
#   DATABASE_URL=postgresql://leilao:<senha>@db:5432/leilao     (host = nome do serviço)
#   REDIS_URL=redis://redis:6379/0
#   MEDIA_ROOT=/srv/media
docker compose up -d --build
docker compose exec backend python manage.py seed_demo
BASE=http://localhost:8080 bash scripts/doctor.sh
```

Atualizar depois de um `git pull`: `docker compose up -d --build` (as migrações rodam na subida do backend).

### O que NÃO pode se perder

- Volume `pgdata` (banco) e volume das fotos (`media`). `docker compose down` mantém os dois;
  **nunca** rode `docker compose down -v` na VM.
- O `.env` da VM (não está no git). Guarde uma cópia fora da VM.

### Diagnóstico rápido na VM

```bash
docker compose ps                       # tudo "healthy"/"running"?
docker compose logs --tail=50 worker    # o worker está passando a cada 1 s?
curl -s localhost:8080/api/health       # {"status":"ok","db":true,"redis":true,...}
timedatectl                             # "System clock synchronized: yes"
df -h /                                 # disco para fotos
```

### Cenário "reinício do sistema" (a banca testa)

```bash
docker compose restart backend worker   # ou: docker compose down && docker compose up -d
```
Depois disso: sessões continuam (ficam no banco), leilões que deveriam ter aberto abrem, os que
passaram do término fecham na primeira passada do worker, as salas reconectam e recebem `snapshot`.
