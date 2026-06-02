# React/FastAPI Migration

## Folder Structure

```text
backend/
  __init__.py
  main.py
  requirements.txt
  schemas.py
  serializers.py
frontend/
  index.html
  package.json
  postcss.config.js
  tailwind.config.js
  tsconfig.json
  vite.config.ts
  src/
    App.tsx
    main.tsx
    styles.css
    types.ts
    api/client.ts
    components/
      AnalysisPanel.tsx
      ChessBoardPanel.tsx
      EvalGraph.tsx
      Header.tsx
      MoveList.tsx
      PgnInput.tsx
```

## Backend

The FastAPI layer reuses the existing PGN and Stockfish analysis code.

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn backend.main:app --reload
```

If port `8000` is already in use:

```powershell
uvicorn backend.main:app --reload --port 8001
```

Endpoints:

- `GET /health`
- `POST /analyze`

Request body:

```json
{
  "pgn": "[Event \"...\"]\n1. e4 c6 ...",
  "depth": 16
}
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

By default, the frontend calls:

```text
http://127.0.0.1:8000
```

Set `VITE_API_BASE_URL` if the API runs elsewhere.

Example for the API on port `8001`:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8001"
npm run dev -- --port 5174
```
