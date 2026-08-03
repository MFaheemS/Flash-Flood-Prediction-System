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

## 1. Backend → Render (free)

1. Go to **https://render.com** → sign in with GitHub.
2. **New → Blueprint** → pick this repo → Render reads `render.yaml` and creates
   the `floodwatch-api` Docker service. Click **Apply**.
   - (Or **New → Web Service → Docker**, same repo, if you prefer manual.)
3. Wait for the build (~5–8 min the first time). You'll get a URL like
   **`https://floodwatch-api.onrender.com`**.
4. Test it: open `https://floodwatch-api.onrender.com/api/meta` — you should get JSON.

**Free-tier note:** the service **sleeps after ~15 min idle**; the next request
cold-starts (~30–60s) and the live-risk snapshot re-warms. Fine for a demo. To
keep it always-on, upgrade to Render's cheapest paid instance or use Fly.io.

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
