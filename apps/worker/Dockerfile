FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    poppler-utils \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 worker
WORKDIR /app/apps/worker

COPY apps/worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN npm install -g @openai/codex

COPY apps/worker ./
USER worker
ENV PYTHONPATH=/app/apps/worker/src
CMD ["python", "-m", "autofacodex.gateway"]
