# NitiClaim — Deployment Guide

## ✅ Streamlit Community Cloud (LIVE)

**Live URL:** [niticlaim.streamlit.app](https://niticlaim.streamlit.app/)

Already deployed. Manage at [share.streamlit.io](https://share.streamlit.io/).

Add secrets under **App Settings → Secrets**:
```toml
PERPLEXITY_API_KEY = "your_api_key_here"
OPENAI_API_KEY = "your_openai_key_here"
```

---

## 🟢 Render (Full-Stack — FastAPI + Streamlit + React)

The repo includes a `render.yaml` Blueprint that auto-configures 3 services.

### Steps
1. Go to [dashboard.render.com](https://dashboard.render.com/) → **New → Blueprint**
2. Connect GitHub repo: `Mradul-Consultancy/NitiClaim`
3. Render auto-detects `render.yaml` and creates:
   - `niticlaim-backend` (FastAPI REST API)
   - `niticlaim-streamlit` (Streamlit Claims Portal)
   - `niticlaim-frontend` (React Static Site)
4. Add environment variables: `PERPLEXITY_API_KEY`, `OPENAI_API_KEY`
5. Click **Apply**

---

## 🟢 Vercel (React Frontend)

The `frontend/` directory includes `vercel.json` for zero-config deploy.

### Steps
1. Go to [vercel.com/new](https://vercel.com/new) → Import from GitHub
2. Select `Mradul-Consultancy/NitiClaim`
3. Set **Root Directory** to `frontend`
4. Framework: Vite, Build: `npm run build`, Output: `dist`
5. Add env var: `VITE_API_BASE_URL` → your Render backend URL
6. Deploy

---

## 🚂 Railway (One-Click)

1. Go to [railway.app](https://railway.app/) → **New Project → Deploy from GitHub**
2. Select `Mradul-Consultancy/NitiClaim`
3. Set start command:
   - **Streamlit:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
   - **FastAPI:** `uvicorn api:app --host 0.0.0.0 --port $PORT`
4. Add env vars in dashboard

---

## 🐳 Docker (Self-Hosted / VPS)

### Quick Start
```bash
git clone https://github.com/Mradul-Consultancy/NitiClaim.git
cd NitiClaim
echo "PERPLEXITY_API_KEY=your-key" > .env
docker-compose up -d --build
```

This starts:
- **FastAPI Backend** → `http://localhost:8000` (Swagger: `/docs`)
- **Streamlit App** → `http://localhost:8501`
- **React Frontend** → `http://localhost:5173`

### Individual Dockerfiles
- `Dockerfile.backend` — FastAPI service
- `Dockerfile.streamlit` — Streamlit portal
- `frontend/Dockerfile` — React workbench

---

## 🤗 Hugging Face Spaces

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces) → Create Space
2. Choose **Streamlit** SDK
3. Upload repo files or connect GitHub
4. Set secrets: `PERPLEXITY_API_KEY`

---

## ☁️ Google Cloud Run

```bash
gcloud run deploy niticlaim-api \
  --source . \
  --dockerfile Dockerfile.backend \
  --port 8000 \
  --allow-unauthenticated \
  --set-env-vars PERPLEXITY_API_KEY=your-key
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PERPLEXITY_API_KEY` | Yes | Perplexity AI API key |
| `OPENAI_API_KEY` | Optional | OpenAI API key (alternative LLM) |
| `DATABASE_URL` | Optional | Default: `sqlite:///./insurance_claims.db` |
| `DEFAULT_LLM_PROVIDER` | Optional | `perplexity`, `openai`, or `mock` |

---

## Troubleshooting

1. **pyarrow build failure on Python 3.14** — Fixed by removing `pyproject.toml`/`uv.lock`. The app uses `requirements.txt` and `runtime.txt` (pinned to Python 3.11).
2. **API Authentication Error (401)** — Verify API keys are set correctly.
3. **Module Import Errors** — Ensure `requirements.txt` deps are installed.
4. **PDF Processing Issues** — Verify PyMuPDF installation (`pymupdf`).