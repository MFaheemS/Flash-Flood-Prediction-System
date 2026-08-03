"""
Hugging Face Space entry point (Gradio SDK — free, no card).

The Gradio SDK Space runs `python app.py`. We import the real FastAPI backend
(all /api/* routes + its background risk-refresh thread), mount a tiny Gradio
landing page onto it so the Space is recognised as a Gradio app, and serve the
whole thing with uvicorn on the Space's port (GRADIO_SERVER_PORT, default 7860).

Result: the same backend, reachable at https://<user>-<space>.hf.space/api/... —
with no Docker and no payment card.
"""
import os

import gradio as gr
import spaces
import uvicorn

# HF's free tier now runs Gradio Spaces on ZeroGPU, which refuses to start
# unless at least one top-level @spaces.GPU function exists — even though this
# CPU-only API never touches a GPU. This no-op satisfies that startup check;
# the FastAPI server itself keeps running on the always-available CPU.
@spaces.GPU
def _zerogpu_noop():
    return "ok"


from src.app import app as api  # FastAPI app: routes + @on_event("startup") refresh

with gr.Blocks(title="FloodWatch API") as demo:
    gr.Markdown(
        "# 🌊 FloodWatch API\n"
        "The FloodWatch flash-flood backend is running on this Space.\n\n"
        "**Endpoints:** `/api/meta` · `/api/risk?horizon=week` · "
        "`/api/risk/point?lat=&lon=` · `/api/weather/current?lat=&lon=` · "
        "`/api/factors?dataset=district_flood`\n\n"
        "The FloodWatch web app (on Cloudflare) points its `VITE_API_BASE_URL` here."
    )

# Mount the Gradio landing page at /ui; the FastAPI routes (incl. "/" and /api/*)
# keep working on the same server.
app = gr.mount_gradio_app(api, demo, path="/ui")

if __name__ == "__main__":
    port = int(os.environ.get("GRADIO_SERVER_PORT", os.environ.get("PORT", 7860)))
    uvicorn.run(app, host="0.0.0.0", port=port)
