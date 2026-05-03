FROM python:3.11-slim

LABEL maintainer="RR_Szatan_Lambert_Kowalczyk_Szostak"
LABEL description="Reproducible research: Intraday Momentum Strategies"

# Prevent Python from writing .pyc and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specification first for better layer caching
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[dev]"

# Copy the rest of the project
COPY . .

# Install the project in editable mode
RUN pip install --no-cache-dir -e .

# Default command: run tests
CMD ["pytest", "--tb=short"]
