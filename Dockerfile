# Build the Vue.js frontend
FROM node:22-slim AS frontend
ARG VITE_API_BASE_URL=http://localhost:80
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
WORKDIR /frontend
COPY rag/web/arxiv_ai_chat/package.json rag/web/arxiv_ai_chat/package-lock.json ./
RUN npm ci
COPY rag/web/arxiv_ai_chat/ ./
RUN npm run build

FROM python:3.11-slim
LABEL authors="glock"
LABEL org.opencontainers.image.title="arxiv-cs_Ai-chat"
LABEL org.opencontainers.image.description="FastAPI server with Vue.js frontend for arXiv AI chat"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /bin/uv

WORKDIR /app

# Install dependencies first so they are cached between code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH"

COPY ./rag /app/rag
COPY --from=frontend /frontend/dist /app/rag/web/arxiv_ai_chat/dist

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "rag.api.api:app", "--host", "0.0.0.0", "--port", "8000"]
