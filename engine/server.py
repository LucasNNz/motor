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

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .backend import build_backend
from .collector_service import collector_service
from .composer_engine import composer_engine
from .memory_manager import memory_manager
from .models import (
    BatchItem,
    BatchStartRequest,
    BatchStatus,
    CollectMissingRequest,
    CollectRequest,
    GenerateRequest,
    MemoryApproveRequest,
    RefinerBenchmarkRequest,
    GuidedCollectRequest,
    GuidedGenerateRequest,
    MemoryUpdateRequest,
    OperationEvaluationRequest,
    OperationReprocessRequest,
    BrowserFinalizeRequest,
)
from .sdcpp_manager import manager as sdcpp_manager
from .refiner import decode_base64_image
from .refiner_benchmark import benchmark_manager
from .guide_parser import guide_parser
from .guided_service import guided_service
from .anatomy_locator import anatomy_locator
from .operation_manager import operation_manager
from .utils import build_zip, parse_prompt_lines
from .runtime_paths import OUTPUTS_DIR as RUNTIME_OUTPUTS_DIR, BENCHMARKS_DIR, IS_VERCEL, runtime_status

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
OUTPUTS_DIR = RUNTIME_OUTPUTS_DIR
STATIC_DIR = BASE_DIR / "static"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Corvo Image Engine", version="0.12.8")
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
            "V0.12.8 é guia-first e browser-first: o refinador principal é executado no navegador via WebGPU/WASM. Backends nativos locais são apenas legado opcional."
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
    info["anatomy"] = anatomy_locator.status()
    info["memory"] = memory_manager.status()
    info["providers"] = collector_service.provider_names()
    return info


def _prompt_missing_map(prompt: str) -> list[dict[str, str]]:
    p = composer_engine.interpreter.interpret(prompt)
    missing = []
    checks = [
        ("background", p.background, p.normalized_prompt),
        ("object", p.object, p.normalized_prompt),
        ("pose", p.pose, "pointing pose" if 'apont' in p.normalized_prompt else None),
        ("face", p.face, "surprised face" if 'surpres' in p.normalized_prompt else None),
        ("outfit", p.outfit, "ninja outfit" if 'ninja' in p.normalized_prompt else None),
    ]
    for type_name, asset, fallback_query in checks:
        if not asset:
            continue
        concept = asset.get('concept') or asset.get('title') or (asset.get('tags') or [type_name])[0]
        if asset.get('source') != 'demo_bank':
            continue
        if memory_manager.search_best(concept=concept, type_name=type_name, limit=1):
            continue
        query = fallback_query or concept
        missing.append({'type': type_name, 'concept': concept, 'query': query})
    return missing


@app.get("/api/health")
def health():
    return {"ok": True, "jobs": len(jobs), "version": "0.12.8", **runtime_status()}


@app.get("/api/deployment/status")
def deployment_status():
    data = runtime_status()
    data.update({
        "version": "0.12.8",
        "sdcpp_local_available": not IS_VERCEL,
        "persistent_library": not IS_VERCEL,
        "note": (
            "No Vercel, a interface/Composer podem executar com armazenamento temporário; "
            "o refinador principal roda no navegador; stable-diffusion.cpp permanece apenas como modo legado local."
            if IS_VERCEL else
            "Modo local: biblioteca persistente disponível; refinador browser continua sendo o caminho principal, com SD.CPP legado opcional."
        ),
    })
    return data


@app.get("/api/browser/config")
def browser_config():
    return {
        "version": "0.12.8",
        "architecture": "browser_first",
        "execution": {
            "preferred": "webgpu",
            "fallback": "wasm",
            "server_inference_required": False,
        },
        "mvp_refiner": {
            "runtime": "transformers.js",
            "runtime_version": "3.8.1",
            "task": "image-to-image",
            "model": "Xenova/swin2SR-lightweight-x2-64",
            "purpose": "browser inference proof + detail reconstruction/super-resolution",
            "generative_guided": False,
        },
        "cache": "browser_cache_api",
        "local_install_required": False,
        "legacy_local_backends": ["sdcpp_local", "diffusers_cpu", "automatic1111"],
    }


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
    if IS_VERCEL:
        raise HTTPException(status_code=503, detail="stable-diffusion.cpp é um processo local e não pode ser iniciado dentro de uma Vercel Function. Use o modo local ou um endpoint remoto.")
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


@app.get("/api/memory/status")
def memory_status():
    return memory_manager.status()


@app.get("/api/memory/items")
def memory_items(
    type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    approved_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
):
    try:
        return {
            'status': memory_manager.status(),
            'items': memory_manager.list_items(type_name=type, query=q, approved_only=approved_only, limit=limit, status=status),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/memory/search")
def memory_search(
    concept: str = Query(...),
    type: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
):
    try:
        return {
            'concept': concept,
            'type': type,
            'items': memory_manager.search_best(concept=concept, type_name=type, limit=limit),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/memory/items/{item_id}/approve")
def memory_approve(item_id: str, req: MemoryApproveRequest):
    try:
        item = memory_manager.approve_item(item_id, approved=req.approved)
        composer_engine.reload_memory()
        return item
    except KeyError:
        raise HTTPException(status_code=404, detail='Item não encontrado')
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/api/memory/items/{item_id}")
def memory_update(item_id: str, req: MemoryUpdateRequest):
    try:
        item = memory_manager.update_item(
            item_id, tags=req.tags, preferred=req.preferred, blocked=req.blocked, metadata=req.metadata,
            type_name=req.type, concept=req.concept
        )
        if req.status:
            item = memory_manager.set_status(item_id, req.status)
        composer_engine.reload_memory()
        return item
    except KeyError:
        raise HTTPException(status_code=404, detail='Item não encontrado')
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/memory/items/{item_id}")
def memory_delete(item_id: str):
    try:
        result = memory_manager.delete_item(item_id)
        composer_engine.reload_memory()
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail='Item não encontrado')


@app.get("/api/memory/items/{item_id}/asset")
def memory_asset(item_id: str):
    item = memory_manager.by_id.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail='Item não encontrado')
    path = memory_manager.path_for(item)
    if not path.exists():
        raise HTTPException(status_code=404, detail='Arquivo local não encontrado')
    return FileResponse(path, media_type='image/png')


@app.post("/api/collect")
def collect(req: CollectRequest):
    try:
        result = collector_service.collect(
            query=req.query,
            type_name=req.type,
            concept=req.concept or req.query,
            providers=req.providers,
            per_provider=req.per_provider,
            save_limit=req.save_limit,
            auto_approve=req.auto_approve,
        )
        composer_engine.reload_memory()
        result['memory'] = memory_manager.status()
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/collect/missing")
def collect_missing(req: CollectMissingRequest):
    try:
        missing = _prompt_missing_map(req.prompt)
        results = []
        for miss in missing:
            results.append(collector_service.collect(
                query=miss['query'],
                type_name=miss['type'],
                concept=miss['concept'],
                providers=req.providers,
                per_provider=req.per_provider,
                save_limit=req.save_limit_per_concept,
                auto_approve=req.auto_approve,
            ))
        composer_engine.reload_memory()
        return {
            'prompt': req.prompt,
            'missing': missing,
            'results': results,
            'memory': memory_manager.status(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/guide/parse")
def parse_guide(payload: dict):
    text = str(payload.get('guide_text') or '')
    if not text.strip():
        raise HTTPException(status_code=400, detail='Guia vazio')
    return guide_parser.parse(text).as_dict()


@app.post("/api/guide/collect")
def collect_guide(req: GuidedCollectRequest):
    try:
        return guided_service.collect_from_guide(req.guide_text, providers=req.providers, auto_approve=req.auto_approve)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/generate/guided")
def generate_guided(req: GuidedGenerateRequest):
    try:
        result = guided_service.execute(
            prompt=req.prompt, guide_text=req.guide_text, width=req.width, height=req.height,
            refiner_name=req.refiner, steps=req.steps, strength=req.strength,
            collect_missing=req.collect_missing, auto_approve_collected=req.auto_approve_collected,
            allow_candidates=req.use_candidates, providers=req.providers, fast_mvp=req.fast_mvp,
        )
        image = result.pop('image')
        result['image_base64'] = image_to_base64_png(image)
        result['export_url'] = f"/api/operations/{result['operation_id']}/export"
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/operations/{operation_id}")
def operation_status(operation_id: str):
    try:
        return operation_manager.status(operation_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Operação não encontrada')


@app.post("/api/operations/{operation_id}/evaluate")
def operation_evaluate(operation_id: str, req: OperationEvaluationRequest):
    try:
        data = req.model_dump(exclude_none=True)
        evaluation = operation_manager.evaluate(operation_id, data)
        if req.approved is not None:
            status = operation_manager.status(operation_id)
            refs = ((status.get('referencias') or {}).get('used') or [])
            ids = [x.get('id') for x in refs if x.get('id') in memory_manager.by_id]
            memory_manager.register_result(ids, approved=req.approved)
        return evaluation
    except KeyError:
        raise HTTPException(status_code=404, detail='Operação não encontrada')
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/operations/{operation_id}/reprocess")
def operation_reprocess(operation_id: str, req: OperationReprocessRequest):
    try:
        result = guided_service.reprocess(
            parent_operation_id=operation_id,
            correction_guide_text=req.correction_guide_text,
            refiner_name=req.refiner,
            steps=req.steps,
            strength=req.strength,
        )
        image = result.pop('image')
        result['image_base64'] = image_to_base64_png(image)
        result['export_url'] = f"/api/operations/{result['operation_id']}/export"
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail='Operação pai ou resultado não encontrado')
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/operations/{operation_id}/browser-finalize")
def operation_browser_finalize(operation_id: str, req: BrowserFinalizeRequest):
    try:
        operation_manager.status(operation_id)
        image = decode_base64_image(req.image_base64)
        operation_manager.save_image(operation_id, 'etapas/depois_refinamento.png', image)
        operation_manager.save_image(operation_id, 'resultado_final.png', image)
        existing = operation_manager.read_json(operation_id, 'logs/refinador.json', {}) or {}
        merged = {**existing, 'browser_finalized': True, 'browser': req.refiner_metadata}
        operation_manager.write_json(operation_id, 'logs/refinador.json', merged)
        operation_manager.write_json(operation_id, 'logs/resultado_cliente.json', {
            'browser_finalized': True, 'width': image.width, 'height': image.height,
            'metadata': req.refiner_metadata, 'at': time.time(),
        })
        return {'ok': True, 'operation_id': operation_id, 'export_url': f'/api/operations/{operation_id}/export'}
    except KeyError:
        raise HTTPException(status_code=404, detail='Operação não encontrada')
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/operations/{operation_id}/export")
def operation_export(operation_id: str):
    try:
        path = operation_manager.export_zip(operation_id)
        return FileResponse(path, filename=path.name, media_type='application/zip')
    except KeyError:
        raise HTTPException(status_code=404, detail='Operação não encontrada')


@app.get("/api/operations/{operation_id}/result")
def operation_result(operation_id: str):
    path = operation_manager.root_for(operation_id) / 'resultado_final.png'
    if not path.exists():
        raise HTTPException(status_code=404, detail='Resultado não encontrado')
    return FileResponse(path, media_type='image/png')


@app.get("/api/refiner/status")
def refiner_status():
    engine = sdcpp_manager.status()
    caps = engine.get('native_capabilities') or {}
    data = caps.get('data') or {}
    features = ((data.get('features_by_mode') or {}).get('img_gen') or data.get('features') or {})
    if not isinstance(features, dict):
        features = {}
    conditioning_features = {
        key: bool(value.get('enabled', True) if isinstance(value, dict) else value)
        for key, value in features.items()
        if key in {'init_image', 'control_image', 'ip_adapter_image', 'ref_images'}
    }
    return {
        'browser_refiner': {
            'available': True,
            'execution_location': 'client_browser',
            'preferred_device': 'webgpu',
            'fallback_device': 'wasm',
            'runtime': 'transformers.js',
            'runtime_version': '3.8.1',
            'model': 'Xenova/swin2SR-lightweight-x2-64',
            'generative_guided': False,
            'local_install_required': False,
        },
        'light_cpu': {'available': True, 'generative': False, 'conditioning': False, 'legacy': True},
        'sdcpp_img2img': {
            'available': bool(engine.get('engine_installed') and engine.get('model_installed')),
            'generative': True,
            'engine': engine,
            'conditioning_features': conditioning_features,
            'visual_conditioning_ready': bool(
                conditioning_features.get('ip_adapter_image')
                or conditioning_features.get('ref_images')
                or conditioning_features.get('control_image')
            ),
        },
        'anatomy': anatomy_locator.status(),
    }


@app.post("/api/refiner/benchmark")
def start_refiner_benchmark(req: RefinerBenchmarkRequest):
    try:
        return benchmark_manager.start(
            backend=req.backend,
            prompts=req.prompts,
            width=req.width,
            height=req.height,
            steps=req.steps,
            strength=req.strength,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/refiner/benchmark/{job_id}")
def get_refiner_benchmark(job_id: str):
    job = benchmark_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Benchmark não encontrado')
    return job


@app.post("/api/refiner/benchmark/{job_id}/cancel")
def cancel_refiner_benchmark(job_id: str):
    if not benchmark_manager.cancel(job_id):
        raise HTTPException(status_code=404, detail='Benchmark não encontrado')
    return {'ok': True, 'job_id': job_id}


@app.get("/api/refiner/benchmark/{job_id}/image/{filename}")
def refiner_benchmark_image(job_id: str, filename: str):
    safe = Path(filename).name
    path = BENCHMARKS_DIR / job_id / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail='Imagem de benchmark não encontrada')
    return FileResponse(path, media_type='image/png')


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
        operation_id = operation_manager.create(prompt=item.prompt, guide_text='')
        item.operation_id = operation_id
        item.export_url = f"/api/operations/{operation_id}/export"
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
            operation_manager.save_image(operation_id, 'resultado_final.png', image)
            operation_manager.save_image(operation_id, 'etapas/composicao_base.png', image)
            operation_manager.save_image(operation_id, 'etapas/antes_refinamento.png', image)
            operation_manager.save_image(operation_id, 'etapas/depois_refinamento.png', image)
            operation_manager.write_json(operation_id, 'logs/buscas.json', [])
            operation_manager.write_json(operation_id, 'logs/composicao.json', item.composition or {})
            operation_manager.write_json(operation_id, 'logs/refinador.json', {'backend': status.backend, 'mode': 'batch_legacy'})
            operation_manager.write_json(operation_id, 'logs/tempos.json', {'total_ms': elapsed_ms})
            operation_manager.write_json(operation_id, 'logs/erros.json', [])
            operation_manager.write_json(operation_id, 'logs/avaliacao.json', {'approved': None, 'scores': {}, 'notes': ''})
            refs = []
            library_ids = []
            plan = ((item.composition or {}).get('plan') or {})
            for label in ['background', 'pose', 'face', 'outfit', 'object']:
                ref = plan.get(label) or {}
                if not ref.get('id'):
                    continue
                row = {'label': label, 'id': ref.get('id'), 'source': ref.get('source'), 'file': ref.get('file')}
                lib_item = memory_manager.by_id.get(ref.get('id'))
                if lib_item:
                    source_path = memory_manager.path_for(lib_item)
                    library_ids.append(ref.get('id'))
                else:
                    asset = next((a for a in composer_engine.bank.assets if a.get('id') == ref.get('id')), None)
                    source_path = composer_engine.bank.asset_path(asset) if asset else PROJECT_DIR / '__missing__'
                row['operation_copy'] = operation_manager.copy_reference(operation_id, source_path, f'{label}_{ref.get("id")}')
                refs.append(row)
            memory_manager.register_operation_use(library_ids, operation_id)
            operation_manager.write_json(operation_id, 'logs/referencias.json', {'used': refs})
            operation_manager.finish(operation_id, status='done', diagnostic='Item de lote concluído; avaliação manual pendente.')
            item.status = "done"
        except Exception as exc:
            item.status = "error"
            item.error = str(exc)
            operation_manager.write_json(operation_id, 'logs/erros.json', [{'stage': 'batch_generate', 'error': str(exc)}])
            operation_manager.finish(operation_id, status='error', diagnostic=str(exc))

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

    if IS_VERCEL:
        if req.backend not in {"mock", "composer", "composer_engine", "corvo_composer"}:
            raise HTTPException(status_code=503, detail="Lote generativo local não é suportado dentro da Vercel Function. Use Composer/Mock ou execute o Engine localmente.")
        run_batch(job_id)
    else:
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
