#!/usr/bin/env bash
# Confere se o ambiente (máquina local ou VM) está pronto. Só LÊ: não muda nada.
#   make doctor                      # local, API em http://localhost:8000
#   BASE=http://localhost:8080 bash scripts/doctor.sh   # na VM, pelo Caddy
set -u
cd "$(dirname "$0")/.."
BASE="${BASE:-http://localhost:8000}"
fails=0
ok()   { printf '  \033[32m✔\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✘\033[0m %s\n' "$1"; fails=$((fails + 1)); }

echo "Ferramentas"
command -v docker >/dev/null && ok "docker: $(docker --version | cut -d, -f1)" || bad "docker não instalado"
if docker info >/dev/null 2>&1; then ok "daemon do docker acessível"
else bad "sem acesso ao docker (usuário fora do grupo docker? tente: newgrp docker)"; fi
docker compose version >/dev/null 2>&1 && ok "docker compose disponível" || bad "docker compose ausente"
if [ -x backend/.venv/bin/python ]; then ok "venv: $(backend/.venv/bin/python --version)"
else warn "backend/.venv não existe (rode: make venv) — só importa em dev local"; fi

echo "Configuração"
if [ -f .env ]; then
  ok ".env existe"
  missing=$(comm -23 <(grep -oE '^[A-Z_]+=' .env.example | sort -u) <(grep -oE '^[A-Z_]+=' .env | sort -u) | tr -d '=' | xargs)
  [ -z "$missing" ] && ok ".env tem todas as chaves do .env.example" || bad ".env sem as chaves: $missing"
  grep -q '^DJANGO_SECRET_KEY=troque-isto' .env && warn "DJANGO_SECRET_KEY ainda é o valor de exemplo (trocar na VM)"
  grep -q '^DJANGO_DEBUG=1' .env && warn "DJANGO_DEBUG=1 (ok em dev; na VM use 0)"
else bad ".env não existe (cp .env.example .env)"; fi
if git ls-files --error-unmatch .env >/dev/null 2>&1; then bad ".env está versionado no git!"
else ok ".env fora do git"; fi

echo "Serviços"
for service in db redis; do
  state=$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk -v s="$service" '$1==s {print $2}')
  [ "$state" = "healthy" ] && ok "$service saudável" || bad "$service não está saudável (estado: ${state:-parado}) — make db"
done
health=$(curl -s -m 5 "$BASE/api/health" || true)
if echo "$health" | grep -q '"status":"ok"'; then ok "API responde em $BASE/api/health (banco e Redis ok)"
elif [ -n "$health" ]; then bad "API degradada: $health"
else bad "API não responde em $BASE (make backend, ou docker compose up na VM)"; fi
if [ -n "$health" ]; then
  code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$BASE/admin/")
  [ "$code" = "404" ] && ok "/admin/ não existe (RF03)" || bad "/admin/ respondeu $code (não pode existir)"
  server=$(echo "$health" | grep -oE '"server_time":"[^"]+"' | cut -d'"' -f4)
  if [ -n "$server" ]; then
    drift=$(( $(date -u +%s) - $(date -u -d "$server" +%s) ))
    [ "${drift#-}" -le 2 ] && ok "relógio do servidor = relógio desta máquina (diferença ${drift}s)" \
      || warn "relógio do servidor difere ${drift}s desta máquina (o cronômetro compensa, mas confira o NTP)"
  fi
fi
if pgrep -f 'manage.py run_auction_worker' >/dev/null || docker compose ps --format '{{.Service}}' 2>/dev/null | grep -q worker; then
  ok "worker rodando"
else warn "worker não está rodando: leilões não abrem nem fecham (make worker)"; fi

echo "Máquina"
if command -v timedatectl >/dev/null; then
  [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = "yes" ] && ok "relógio sincronizado por NTP" \
    || warn "relógio SEM sincronia NTP: horários de abertura/fechamento podem parecer errados para a banca"
fi
free_mb=$(df -Pm . | awk 'NR==2 {print $4}')
[ "$free_mb" -gt 1024 ] && ok "disco livre: ${free_mb} MB" || bad "pouco disco livre: ${free_mb} MB (fotos e imagens docker)"
if command -v ss >/dev/null; then
  ss -ltn 2>/dev/null | grep -q ':8080 ' && ok "algo escuta na 8080 (porta pública da VM)" \
    || warn "nada escuta na 8080 (normal em dev; na VM é o Caddy)"
fi
behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
[ "$behind" = "0" ] && ok "branch em dia com origin/main (último fetch)" || warn "branch $behind commit(s) atrás de origin/main"

echo
if [ "$fails" -eq 0 ]; then printf '\033[32mTudo certo.\033[0m\n'; else printf '\033[31m%s problema(s).\033[0m\n' "$fails"; exit 1; fi
