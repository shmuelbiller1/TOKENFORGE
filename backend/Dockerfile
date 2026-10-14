FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TIKTOKEN_CACHE_DIR=/opt/tiktoken
WORKDIR /app

COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt \
 && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

COPY . .
EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
