FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# no-cache-bust 2026-10-07
COPY . .
ENV PORT=8000
EXPOSE 8000
CMD ["python", "server.py"]
