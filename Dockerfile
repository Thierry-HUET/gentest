FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Installation de Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
 && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

COPY pyproject.toml poetry.lock* ./

# Installation des dépendances (sans créer de virtualenv dans le conteneur)
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --only main

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "src/gentest/app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.enableStaticServing=true"]
