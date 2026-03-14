# Lens

Upload images, get automatic AI analysis (object detection, scene classification, person identification), then search and investigate your collection using natural language.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- [OpenRouter API key](https://openrouter.ai/keys)

## Setup

### 1. Backend

```bash
cd backend
cp .env.example .env.local
# Edit .env.local and add your OPENROUTER_API_KEY
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
uv sync
uv run streamlit run app.py
```

Frontend runs at `http://localhost:8501`.

> **Note:** If the backend runs on a port other than 8000, update `API_BASE` in `frontend/api_client.py`.

## Project Structure

```
lens/
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models (Image, ImageAnalysis, Investigation)
│   │   ├── routes/          # API endpoints (images, analysis, search, investigate)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── services/        # Core logic (vision, embeddings, FTS, hashing, LLM)
│   ├── main.py              # FastAPI app entry point
│   └── .env.example         # Environment variable template
├── frontend/
│   ├── pages/               # Streamlit pages
│   │   ├── 1_Dashboard.py
│   │   ├── 2_Library.py
│   │   ├── 3_Search.py
│   │   ├── 4_Investigation.py
│   │   └── 5_Duplicates.py
│   ├── app.py               # Streamlit entry point
│   ├── api_client.py        # Backend API client
│   └── components.py        # Shared UI components
└── README.md
```

## API Endpoints

| Method | Path                    | Description                    |
| ------ | ----------------------- | ------------------------------ |
| GET    | `/images`               | List all images                |
| POST   | `/images/upload`        | Upload images                  |
| POST   | `/images/import-folder` | Import from local folder       |
| POST   | `/images/{id}/analyze`  | Analyze a single image         |
| POST   | `/images/reindex`       | Re-analyze all images          |
| POST   | `/search/images`        | Hybrid search                  |
| POST   | `/investigate`          | Natural language investigation |
| GET    | `/duplicates`           | Find duplicate images          |
| GET    | `/health`               | Health check                   |

## License

Proprietary — Ardenta Corp.
