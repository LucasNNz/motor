from __future__ import annotations

import json
import statistics
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from .composer_engine import composer_engine
from .refiner import SdCppImg2ImgRefiner, build_refiner

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / 'outputs' / 'refiner_benchmarks'
OUTPUTS.mkdir(parents=True, exist_ok=True)

DEFAULT_PROMPTS = [
    'UM GARFO COMO ELEMENTO PRINCIPAL, CENTRALIZADO, FUNDO CLARO E SIMPLES, ILUSTRAÇÃO 2D SEMIRREALISTA LIMPA, SEM TEXTO, SEM LOGOS.',
    'UMA MAÇÃ VERMELHA CENTRALIZADA, BEM DESTACADA, FUNDO CLARO, ILUSTRAÇÃO 2D SEMIRREALISTA LIMPA, SEM TEXTO.',
    'UM MENINO NINJA SURPRESO APONTANDO PARA UMA CAIXA EM UMA FLORESTA, ILUSTRAÇÃO 2D SEMIRREALISTA LIMPA, SEM TEXTO.',
    'UMA BOLA DE FUTEBOL EM UM CAMPO, ELEMENTO PRINCIPAL BEM DESTACADO, ILUSTRAÇÃO 2D LIMPA, SEM TEXTO.',
    'UM CACHORRO FELIZ EM UM PARQUE, COMPOSIÇÃO LIMPA PARA QUIZ, ILUSTRAÇÃO 2D SEMIRREALISTA, SEM TEXTO.',
]


class RefinerBenchmarkManager:
    def __init__(self):
        self.jobs: dict[str, dict[str, Any]] = {}
        self.cancel_flags: dict[str, bool] = {}
        self.lock = threading.Lock()

    def start(
        self,
        *,
        backend: str,
        prompts: Optional[list[str]] = None,
        width: int = 512,
        height: int = 512,
        steps: int = 3,
        strength: float = 0.24,
    ) -> dict[str, Any]:
        job_id = uuid.uuid4().hex[:10]
        prompts = [p.strip() for p in (prompts or DEFAULT_PROMPTS) if p.strip()]
        if not prompts:
            prompts = list(DEFAULT_PROMPTS)
        prompts = prompts[:10]
        job = {
            'job_id': job_id,
            'status': 'pending',
            'backend': backend,
            'width': width,
            'height': height,
            'steps': steps,
            'strength': strength,
            'prompts': prompts,
            'total': len(prompts),
            'completed': 0,
            'failed': 0,
            'engine_start_ms': None,
            'engine_status': None,
            'items': [],
            'summary': None,
            'started_at': time.time(),
            'finished_at': None,
            'output_dir': str(OUTPUTS / job_id),
        }
        self.jobs[job_id] = job
        self.cancel_flags[job_id] = False
        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        thread.start()
        return dict(job)

    def get(self, job_id: str) -> Optional[dict[str, Any]]:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str):
        if job_id not in self.jobs:
            return False
        self.cancel_flags[job_id] = True
        return True

    def _process_ram_mb(self) -> Optional[float]:
        try:
            import psutil
            process = psutil.Process()
            return round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return None

    def _engine_ram_mb(self) -> Optional[float]:
        try:
            import psutil
            from .sdcpp_manager import manager as sdcpp_manager
            pid = sdcpp_manager.state.pid
            if not pid:
                return None
            process = psutil.Process(pid)
            return round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return None

    def _run(self, job_id: str):
        job = self.jobs[job_id]
        job['status'] = 'running'
        output_dir = OUTPUTS / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        refiner = build_refiner(job['backend'])

        if isinstance(refiner, SdCppImg2ImgRefiner):
            try:
                status, start_ms = refiner.ensure_engine()
                job['engine_start_ms'] = start_ms
                job['engine_status'] = status
            except Exception as exc:
                job['status'] = 'error'
                job['failed'] = job['total']
                job['summary'] = {'error': str(exc)}
                job['finished_at'] = time.time()
                return
        else:
            job['engine_start_ms'] = 0
            job['engine_status'] = {'mode': 'light_cpu', 'ready': True}

        for index, prompt in enumerate(job['prompts'], start=1):
            if self.cancel_flags.get(job_id):
                job['status'] = 'cancelled'
                break
            item = {
                'index': index,
                'prompt': prompt,
                'status': 'running',
                'composer_ms': None,
                'refiner_ms': None,
                'total_ms': None,
                'before_file': None,
                'after_file': None,
                'ram_before_mb': self._process_ram_mb(),
                'ram_after_mb': None,
                'engine_ram_mb': self._engine_ram_mb(),
                'error': None,
            }
            job['items'].append(item)
            try:
                total_started = time.perf_counter()
                compose_started = time.perf_counter()
                before = composer_engine.generate(prompt, job['width'], job['height'])
                item['composer_ms'] = int((time.perf_counter() - compose_started) * 1000)
                before_name = f'{index:02d}_before.png'
                before.save(output_dir / before_name, format='PNG')
                item['before_file'] = before_name

                result = refiner.refine(
                    before,
                    prompt,
                    strength=job['strength'],
                    steps=job['steps'],
                    seed=1000 + index,
                )
                after_name = f'{index:02d}_after.png'
                result.image.save(output_dir / after_name, format='PNG')
                item['after_file'] = after_name
                item['refiner_ms'] = result.duration_ms
                item['total_ms'] = int((time.perf_counter() - total_started) * 1000)
                item['ram_after_mb'] = self._process_ram_mb()
                item['engine_ram_mb'] = self._engine_ram_mb()
                item['metadata'] = result.metadata
                item['status'] = 'done'
                job['completed'] += 1
            except Exception as exc:
                item['status'] = 'error'
                item['error'] = str(exc)
                item['ram_after_mb'] = self._process_ram_mb()
                item['engine_ram_mb'] = self._engine_ram_mb()
                job['failed'] += 1

            self._write_manifest(job_id)

        if job['status'] != 'cancelled':
            if job['completed'] == 0 and job['failed']:
                job['status'] = 'error'
            else:
                job['status'] = 'done'
        job['finished_at'] = time.time()
        job['summary'] = self._summarize(job)
        self._write_manifest(job_id)

    def _summarize(self, job: dict[str, Any]) -> dict[str, Any]:
        done = [x for x in job['items'] if x.get('status') == 'done']
        times = [x['refiner_ms'] for x in done if x.get('refiner_ms') is not None]
        warm = times[1:] if len(times) > 1 else times
        baseline_flow_ms = 32000
        if not times:
            return {
                'completed': 0,
                'failed': job['failed'],
                'engine_start_ms': job.get('engine_start_ms'),
                'baseline_flow_ms': baseline_flow_ms,
                'verdict': 'SEM DADOS',
            }
        avg = statistics.mean(times)
        warm_avg = statistics.mean(warm) if warm else avg
        p = {
            'completed': len(done),
            'failed': job['failed'],
            'engine_start_ms': job.get('engine_start_ms'),
            'first_refiner_ms': times[0],
            'avg_refiner_ms': round(avg, 2),
            'warm_avg_refiner_ms': round(warm_avg, 2),
            'min_refiner_ms': min(times),
            'max_refiner_ms': max(times),
            'baseline_flow_ms': baseline_flow_ms,
            'estimated_vs_flow_ratio': round(warm_avg / baseline_flow_ms, 3),
        }
        if warm_avg <= 10000:
            verdict = 'EXCELENTE'
        elif warm_avg <= 20000:
            verdict = 'MUITO PROMISSOR'
        elif warm_avg <= 30000:
            verdict = 'VIÁVEL PARA TESTE'
        elif warm_avg <= 45000:
            verdict = 'LIMÍTROFE'
        else:
            verdict = 'LENTO DEMAIS PARA O FLUXO ATUAL'
        p['verdict'] = verdict
        return p

    def _write_manifest(self, job_id: str):
        job = self.jobs[job_id]
        output_dir = OUTPUTS / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / 'benchmark.json').write_text(
            json.dumps(job, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )


benchmark_manager = RefinerBenchmarkManager()
