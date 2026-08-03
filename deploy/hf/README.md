---
title: FloodWatch API
emoji: 🌊
colorFrom: blue
colorTo: green
sdk: gradio
app_file: app.py
pinned: false
---

# FloodWatch API

Backend for the FloodWatch flash-flood risk app. It serves a JSON API under
`/api/*` (e.g. `/api/meta`, `/api/risk`, `/api/factors`) and a small landing
page at `/ui`. The FloodWatch web frontend (hosted on Cloudflare) calls this
Space via its `VITE_API_BASE_URL`.
