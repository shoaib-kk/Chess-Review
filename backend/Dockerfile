FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STOCKFISH_PATH=/usr/games/stockfish

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY game_analyzer.py models.py opening_recognition.py pgn_parser.py stockfish_engine.py ./
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

RUN chmod +x backend/entrypoint.sh

EXPOSE 8001

CMD ["bash", "backend/entrypoint.sh"]
