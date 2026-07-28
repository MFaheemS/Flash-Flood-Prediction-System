# Running the app (backend + Lovable frontend)

Two processes: the FastAPI backend (port **8000**) and the Lovable frontend
dev server (port **8080**). They must both be running for the app to work.
The frontend reads the backend URL from `Lovable frontend/.env`
(`VITE_API_BASE_URL=http://localhost:8000`).

## 1. Backend (FastAPI)

```bash
cd "Cloud burst project"
venv\Scripts\activate            # Windows
uvicorn src.app:app --port 8000
```

First load takes ~30–60s while it computes the initial district risk
snapshot in the background; the frontend shows a "Warming up…" state and
auto-retries until it's ready.

## 2. Frontend (Lovable / TanStack Start)

```bash
cd "Cloud burst project/Lovable frontend"
npm install        # first time only
npm run dev        # serves http://localhost:8080
```

Open **http://localhost:8080**.

## Ports — why 8000 + 8080

The Lovable dev server is hard-configured to port 8080, so the backend uses
8000 to avoid a collision. If you deploy the backend somewhere else, update
`VITE_API_BASE_URL` in `Lovable frontend/.env` and restart `npm run dev`
(Vite only reads env vars at startup).

## Deploying (making it shareable)

A Lovable site hosted on **https** cannot call an **http://localhost** API
(browser mixed-content rule). To share the site, deploy the backend to a
public HTTPS host (Render / Railway / Fly.io) and set `VITE_API_BASE_URL`
to that URL. CORS is already open on the backend, so no further change is
needed. Ask me to add a Dockerfile / render.yaml if you want one-click deploy.

## The three factor-analysis models

The `/factors` page has three tabs, each backed by a trained model:
- **cloudburst** (Pakistan) and **flood_factors** (Kaggle) — ready.
- **global_flood** (600 events, ~400 countries) — returns 503 until its
  model finishes training; the tab shows a friendly "still being built"
  state until then, then works automatically (no restart needed).
