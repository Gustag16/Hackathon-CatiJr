# Uma imagem para o servidor ASGI e para o worker (o comando muda no compose).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --system --uid 1001 app && mkdir -p /srv/media && chown app /srv/media
USER app

EXPOSE 8000
# Worker: command: python manage.py run_auction_worker
CMD ["sh", "-c", "python manage.py migrate --noinput && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
