from __future__ import annotations

import base64
import io
import json
import platform
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .backend import build_backend
from .composer_engine import composer_engine
from .models import BatchItem, BatchStartRequest, BatchStatus, GenerateRequest
from .sdcpp_manager import manager as sdcpp_manager
from .utils import build_zip, parse_prompt_lines

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
OUTPUTS_DIR = PROJECT_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Image Motor MVP", version="0.4.0")
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


def _windows_gpu_names() -> list[str]:
    if platform.system().lower() != "windows":
        return []
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        pass
    return []


def get_system_info():
    info = {
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "gpu_names": _windows_gpu_names(),
        "torch_installed": False,
        "cuda_available": False,
        "diffusers_installed": False,
        "recommended_backend": "composer",
        "notes": [
            "CUDA não é obrigatório. O backend recomendado agora é o Composer Engine; geração pesada fica como refinador opcional futuro."
        ],
    }
    try:
        import torch
        info["torch_installed"] = True
        info["cuda_available"] = bool(torch.cuda.is_available())
    except Exception:
        pass

    try:
        import diffusers  # noqa: F401
        info["diffusers_installed"] = True
    except Exception:
        pass

    info["sdcpp"] = sdcpp_manager.status()
    return info


@app.get("/api/health")
def health():
    return {"ok": True, "jobs": len(jobs), "version": "0.4.0"}


@app.get("/api/system")
def system_info():
    return get_system_info()


@app.get("/api/composer/status")
def composer_status():
    return composer_engine.status()


@app.post("/api/composer/rebuild-demo")
def composer_rebuild_demo():
    try:
        return composer_engine.rebuild_demo_bank()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/engine/status")
def engine_status():
    return sdcpp_manager.status()


@app.post("/api/engine/start")
def engine_start():
    try:
        return sdcpp_manager.start()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/engine/stop")
def engine_stop():
    try:
        return sdcpp_manager.stop()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/generate")
def generate(req: GenerateRequest):
    try:
        backend = build_backend(req.backend, req.engine_url)
        started = time.perf_counter()
        image = backend.generate(req.prompt, req.width, req.height, req.seed, req.steps)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "backend": backend.name,
            "duration_ms": elapsed_ms,
            "image_base64": image_to_base64_png(image),
            "composition": getattr(backend, "last_info", None),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def run_batch(job_id: str):
    with job_lock:
        status = jobs[job_id]
        status.status = "running"

    try:
        backend = build_backend(status.backend, status.engine_url)
    except Exception as exc:
        status.status = "error"
        status.failed = len(status.items)
        for item in status.items:
            item.status = "error"
            item.error = str(exc)
        status.finished_at = time.time()
        return

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
            item.composition = getattr(backend, "last_info", None)
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
        raise HTTPException(status_code=400, detail="Nenhum prompt encontrado no texto.")

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
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return status.model_dump()


@app.post("/api/batch/{job_id}/cancel")
def cancel_batch(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    job_cancel_flags[job_id] = True
    return {"ok": True, "job_id": job_id}


@app.get("/api/batch/{job_id}/zip")
def download_zip(job_id: str):
    job_dir = OUTPUTS_DIR / job_id
    zip_path = job_dir / f"{job_id}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP ainda não está pronto")
    return FileResponse(zip_path, filename=zip_path.name, media_type="application/zip")


@app.get("/api/batch/{job_id}/image/{filename}")
def get_image(job_id: str, filename: str):
    path = OUTPUTS_DIR / job_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(path, media_type="image/png")


if (STATIC_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
