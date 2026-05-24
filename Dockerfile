FROM python:3.11-slim

LABEL maintainer="RR_Szatan_Lambert_Kowalczyk_Szostak"
LABEL description="Reproducible research: Intraday Momentum Strategies"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[dev]"

CMD ["python", "-m", "strategy_development.local_implementation.reproduce"]
