FROM python:3.11-slim
LABEL authors="glock"
LABEL org.opencontainers.image.title="arxiv-cs_Ai-chat"
LABEL org.opencontainers.image.description="FastAPI server with Vue.js frontend for arXiv AI chat"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_CREATE=false
ENV PATH="$POETRY_HOME/bin:$PATH"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy project files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-root

# Copy the application code and Vue.js build
COPY ./rag /app/rag

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "rag.api.api:app", "--host", "0.0.0.0", "--port", "8000"]