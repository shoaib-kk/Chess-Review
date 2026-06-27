FROM python:3.12-slim

RUN apt-get update && apt-get install -y stockfish && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY game_analyzer.py models.py opening_recognition.py pgn_parser.py stockfish_engine.py ./
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

RUN chmod +x backend/entrypoint.sh

ENV STOCKFISH_PATH=/usr/games/stockfish

# Applies migrations (alembic upgrade head) before launching uvicorn. Requires
# DATABASE_URL to point at a reachable PostgreSQL instance. Honors $PORT.
CMD ["bash", "backend/entrypoint.sh"]
