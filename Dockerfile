FROM python:3.11-slim

LABEL maintainer="RR_Szatan_Lambert_Kowalczyk_Szostak"
LABEL description="Reproducible research: Intraday Momentum Strategies"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONPATH=/app

WORKDIR /app

ARG QUARTO_VERSION=1.5.57

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        tzdata \
        wget \
    && ARCH=$(dpkg --print-architecture) \
    && wget -q https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-${ARCH}.deb \
    && dpkg -i quarto-${QUARTO_VERSION}-linux-${ARCH}.deb \
    && rm quarto-${QUARTO_VERSION}-linux-${ARCH}.deb \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[dev,report]"

CMD ["/bin/sh", "scripts/render_report.sh"]
