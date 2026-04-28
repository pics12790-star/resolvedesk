FROM node:22-bookworm-slim AS frontend
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY resolvedesk/ resolvedesk/
COPY data/ data/
COPY evals/ evals/
COPY --from=frontend /web/dist apps/web/dist
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn resolvedesk.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
