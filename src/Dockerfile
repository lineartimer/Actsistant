# The Actsistant API. Weaviate and Ollama run in containers of their own,
# see docker-compose.yml.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin app && chown -R app:app /app
USER app

EXPOSE 5005

# The healthcheck is defined in docker-compose.yml

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5005"]
