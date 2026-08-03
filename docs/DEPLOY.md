# Deploying FloodWatch (fully free)

Two pieces:
- **Backend** (FastAPI/Python) → **Render** (free Docker web service) → HTTPS URL
- **Frontend** (TanStack Start → Cloudflare Worker) → **Cloudflare** → HTTPS URL

Everything needed is already in the repo: `Dockerfile`, `render.yaml`,
`requirements-deploy.txt`, `.dockerignore`, and the runtime model/data files.

---

## 0. One-time: push to GitHub

```bash
git add -A
git commit -m "Deploy setup"
git push -u origin clean-district-model-and-ui   # or main
```

(The `.gitignore` already keeps only the small runtime models/CSVs the API
needs — the big datasets, videos source, and GEE exports stay out.)

---

## 1. Backend → a free Docker host

The Dockerfile works on any Docker host. Pick one — **no card options first**.

### Option A (no card, recommended) — Hugging Face **Gradio** Space
HF's Docker SDK now needs a card, but the **Gradio SDK is free with no card**.
We ship a tiny wrapper (`deploy/hf/app.py`) that runs the real FastAPI backend
inside a Gradio Space — **verified working** (all `/api/*` routes + the
background refresh run normally). It only idles after ~48h, so it's effectively
always-on.

1. Sign up at **https://huggingface.co** (free, no card). Create an **access
   token**: Settings → Access Tokens → New token (role: *write*).
2. **New → Space** → name `floodwatch-api` → **SDK: Gradio** → **Blank** → Create.
3. Put the backend + wrapper into that Space repo (in a terminal):
   ```bash
   git clone https://huggingface.co/spaces/<your-user>/floodwatch-api hf-space
   cd hf-space
   # the Gradio wrapper (app.py / requirements.txt / README.md with the right header):
   cp ../deploy/hf/app.py ../deploy/hf/requirements.txt ../deploy/hf/README.md .
   # the backend the API loads:
   cp ../config.yaml .
   cp -r ../src .
   mkdir -p models data/raw
   cp ../models/district_flood_model.pkl ../models/district_flood_model_calibrated.pkl \
      ../models/satellite_flood_model.pkl ../models/cloudburst_model.pkl models/
   cp ../data/raw/district_flood_dataset.csv ../data/raw/satellite_flood_dataset.csv \
      ../data/raw/cloudburst_dataset.csv data/raw/
   git add -A && git commit -m "FloodWatch backend" && git push
   ```
   When `git push` asks for a password, paste your **HF access token**.
4. Open the Space — it builds (~5–8 min) then shows a "🌊 FloodWatch API" page.
   Your API base URL is **`https://<your-user>-floodwatch-api.hf.space`**.
   Test **`…hf.space/api/meta`** → JSON.

> Space repo layout after copying: `app.py`, `requirements.txt`, `README.md`,
> `config.yaml`, `src/`, `models/` (4 files), `data/raw/` (3 CSVs).

### Option B (no card, git-connected) — Koyeb
1. **https://koyeb.com** → sign up with GitHub (free "Hobby").
2. **Create Service → GitHub** → this repo → it detects the `Dockerfile` → free
   instance → Deploy. You get an HTTPS URL. (May ask for a card on some accounts.)

### Option C — Render (needs a card even on free)
If you get a card later: **New → Blueprint** → this repo (uses `render.yaml`) → Apply.

**Sleep note:** the HF Gradio Space idles only after ~48h. Koyeb/Render free
sleep sooner — the keep-alive workflow (step 4) covers those.

---

## 2. Frontend → Cloudflare (free)

The build produces a Cloudflare Worker (`.output/server/wrangler.json`) that
also serves the static assets (videos, map data). Two ways to deploy:

### Option A — Cloudflare dashboard, connected to Git (recommended)
1. **https://dash.cloudflare.com** → **Workers & Pages → Create → Workers → Connect to Git**.
2. Pick this repo. Set:
   - **Root directory:** `Lovable frontend`
   - **Build command:** `npm run build`
   - **Deploy command:** `npx wrangler deploy` (usually auto-detected)
3. Add an **environment variable** (Build + Runtime):
   - `VITE_API_BASE_URL` = your Render URL, e.g. `https://floodwatch-api.onrender.com`
4. Deploy → you get **`https://<name>.workers.dev`**.

### Option B — from your machine (wrangler CLI)
```bash
cd "Lovable frontend"
# point the build at the deployed backend:
echo "VITE_API_BASE_URL=https://floodwatch-api.onrender.com" > .env
npm run build
npx wrangler login          # opens a browser to authorize (free Cloudflare account)
npx wrangler deploy -c .output/server/wrangler.json
```

> ⚠️ `VITE_API_BASE_URL` is baked in **at build time**. If you change the backend
> URL later, set the env var and **rebuild + redeploy**.

**Asset limit:** Cloudflare caps individual files at 25 MB. Your videos are all
< 12 MB after compression, so they're fine.

---

## 3. A free domain (optional)

- **Simplest:** use the free `*.workers.dev` (frontend) and `*.onrender.com`
  (backend) URLs — real HTTPS, nothing to buy.
- **Free real domain:** the **GitHub Student Developer Pack**
  (education.github.com/pack) includes a free `.me` (Namecheap, 1 yr) and a free
  `.tech` (get.tech). After claiming one, add it as a **Custom Domain** on the
  Cloudflare Worker (Workers & Pages → your worker → Settings → Domains).
- Also free: **js.org** (subdomain via a GitHub PR).

---

## 4. Post-deploy checklist

- [ ] `https://<backend>/api/meta` returns JSON.
- [ ] `https://<backend>/api/risk?horizon=week` returns districts (may 503 for
      ~60s on first hit while it warms — that's expected).
- [ ] Frontend loads; **Districts/Map** show risk (confirms it's reaching the backend).
- [ ] **Explore** map loads (confirms `pak_map.json` / videos served by the worker).
- [ ] Browser console has no CORS errors (CORS is open on the backend, so there
      shouldn't be any).

---

## 5. If something's off

- **Frontend loads but no risk data / CORS error:** `VITE_API_BASE_URL` wasn't
  set (or was set after the build). Set it and rebuild/redeploy.
- **Backend build fails on Render:** confirm it's using **Docker** runtime (from
  `render.yaml`), not a Python buildpack.
- **Backend slow first load:** free-tier cold start — expected; refresh after a
  minute.
- **Videos missing on Explore/Home:** ensure `Lovable frontend/public/videos/`
  was committed (they're compressed and tracked).
