FROM python:3.12-slim

RUN apt-get update && apt-get install -y stockfish && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY game_analyzer.py models.py opening_recognition.py pgn_parser.py stockfish_engine.py ./

ENV STOCKFISH_PATH=/usr/games/stockfish

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8001}
