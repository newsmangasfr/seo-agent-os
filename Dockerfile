# Agent OS — Agent de création de contenu IA multi-sites
FROM python:3.11-slim

WORKDIR /app

# dépendances (stdlib only — requirements vide, install no-op sûr)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# code de l'application
COPY . .

ENV PORT=8000
VOLUME ["/app/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/stats',timeout=4).status==200 else 1)"

CMD ["python", "server.py"]
