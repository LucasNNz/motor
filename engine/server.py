from __future__ import annotations

import base64
import io
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from .backend import build_backend
    from .models import BatchItem, BatchStartRequest, BatchStatus, GenerateRequest
    from .utils import build_zip, parse_prompt_lines
except ImportError:  # allows `uvicorn server:app` from inside engine/
    from backend import build_backend
    from models import BatchItem, BatchStartRequest, BatchStatus, GenerateRequest
    from utils import build_zip, parse_prompt_lines

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
import os

# Vercel Functions have an ephemeral writable /tmp. Local runs keep outputs in the project.
OUTPUTS_DIR = Path("/tmp/image_motor_outputs") if os.environ.get("VERCEL") else (PROJECT_DIR / "outputs")
STATIC_DIR = BASE_DIR / "static"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Image Motor MVP", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: Dict[str, BatchStatus] = {}
job_cancel_flags: Dict[str, bool] = {}
job_lock = threading.Lock()


def image_to_base64_png(image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def get_system_info():
    info = {
        "torch_installed": False,
        "cuda_available": False,
        "cuda_device_count": 0,
        "cuda_device_name": None,
        "mps_available": False,
        "recommended_backend": "mock",
        "notes": [],
    }
    try:
        import torch
        info["torch_installed"] = True
        info["cuda_available"] = bool(torch.cuda.is_available())
        if info["cuda_available"]:
            info["cuda_device_count"] = torch.cuda.device_count()
            info["cuda_device_name"] = torch.cuda.get_device_name(0)
            info["recommended_backend"] = "diffusers"
        try:
            info["mps_available"] = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        except Exception:
            info["mps_available"] = False
        if not info["cuda_available"]:
            info["notes"].append("CUDA não detectada neste ambiente. Um backend local real provavelmente dependerá de GPU no PC alvo.")
    except Exception:
        info["notes"].append("PyTorch não detectado corretamente.")

    try:
        import diffusers  # noqa: F401
        info["diffusers_installed"] = True
    except Exception:
        info["diffusers_installed"] = False
        info["notes"].append("'diffusers' ainda não está disponível neste ambiente.")

    return info


@app.get("/api/health")
def health():
    return {"ok": True, "jobs": len(jobs)}


@app.get("/api/system")
def system_info():
    return get_system_info()


@app.post("/api/generate")
def generate(req: GenerateRequest):
    backend = build_backend(req.backend, req.engine_url)
    started = time.perf_counter()
    image = backend.generate(req.prompt, req.width, req.height, req.seed, req.steps)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "backend": backend.name,
        "duration_ms": elapsed_ms,
        "image_base64": image_to_base64_png(image),
    }



def run_batch(job_id: str):
    with job_lock:
        status = jobs[job_id]
        status.status = "running"
    backend = build_backend(status.backend, status.engine_url)
    job_dir = OUTPUTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    for item in status.items:
        if job_cancel_flags.get(job_id):
            item.status = "cancelled"
            continue

        item.status = "running"
        try:
            started = time.perf_counter()
            image = backend.generate(item.prompt, status.width, status.height, None, status.steps)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            filename = f"{item.id}.png"
            output_path = job_dir / filename
            image.save(output_path, format="PNG")
            item.output_file = filename
            item.duration_ms = elapsed_ms
            item.status = "done"
        except Exception as exc:
            item.status = "error"
            item.error = str(exc)

        status.completed = sum(1 for x in status.items if x.status == "done")
        status.failed = sum(1 for x in status.items if x.status == "error")

        manifest = {
            "job_id": status.job_id,
            "status": status.status,
            "completed": status.completed,
            "failed": status.failed,
            "backend": status.backend,
            "engine_url": status.engine_url,
            "items": [x.model_dump() for x in status.items],
        }
        (job_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    status.finished_at = time.time()
    if job_cancel_flags.get(job_id):
        status.status = "cancelled"
    elif status.failed and not status.completed:
        status.status = "error"
    else:
        status.status = "done"

    zip_path = job_dir / f"{job_id}.zip"
    build_zip(job_dir, zip_path)
    status.zip_ready = zip_path.exists()


@app.post("/api/batch")
def start_batch(req: BatchStartRequest):
    entries = parse_prompt_lines(req.text)
    if not entries:
        raise HTTPException(status_code=400, detail="No prompts found in the provided text.")

    job_id = uuid.uuid4().hex[:10]
    items = [BatchItem(id=item_id, prompt=prompt) for item_id, prompt in entries]
    status = BatchStatus(
        job_id=job_id,
        status="pending",
        backend=req.backend,
        engine_url=req.engine_url,
        width=req.width,
        height=req.height,
        steps=req.steps,
        items=items,
        started_at=time.time(),
        total=len(items),
        completed=0,
        failed=0,
        zip_ready=False,
    )
    jobs[job_id] = status
    job_cancel_flags[job_id] = False

    thread = threading.Thread(target=run_batch, args=(job_id,), daemon=True)
    thread.start()
    return status.model_dump()


@app.get("/api/batch/{job_id}")
def get_batch_status(job_id: str):
    status = jobs.get(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status.model_dump()


@app.post("/api/batch/{job_id}/cancel")
def cancel_batch(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job_cancel_flags[job_id] = True
    return {"ok": True, "job_id": job_id}


@app.get("/api/batch/{job_id}/zip")
def download_zip(job_id: str):
    job_dir = OUTPUTS_DIR / job_id
    zip_path = job_dir / f"{job_id}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP not ready")
    return FileResponse(zip_path, filename=zip_path.name, media_type="application/zip")


@app.get("/api/batch/{job_id}/image/{filename}")
def get_image(job_id: str, filename: str):
    path = OUTPUTS_DIR / job_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")


if (STATIC_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
