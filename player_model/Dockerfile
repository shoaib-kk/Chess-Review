# Shared image for both the API and the Celery worker.
FROM python:3.12-slim

# Stockfish for the worker; harmless in the API image too.
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*

ENV STOCKFISH_PATH=/usr/games/stockfish \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY player_model/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The package is imported as `player_model`, so copy it under that path.
COPY player_model ./player_model

# Default command is the API; the worker service overrides it in compose.
CMD ["uvicorn", "player_model.api:app", "--host", "0.0.0.0", "--port", "8000"]
