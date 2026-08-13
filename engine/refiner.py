from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests
from PIL import Image, ImageEnhance, ImageFilter

from .reference_conditioning import VisualReferenceBundle
from .sdcpp_manager import manager as sdcpp_manager


def image_to_base64_png(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.convert('RGB').save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def decode_base64_image(encoded: str) -> Image.Image:
    if ',' in encoded and encoded.startswith('data:'):
        encoded = encoded.split(',', 1)[1]
    raw = base64.b64decode(encoded)
    return Image.open(io.BytesIO(raw)).convert('RGB')


@dataclass
class RefineResult:
    image: Image.Image
    backend: str
    duration_ms: int
    metadata: dict[str, Any]


class LightRefiner:
    """Cheap CPU-only baseline. This is not generative; it exists as a speed/quality floor."""

    name = 'light_cpu'

    def refine(
        self,
        image: Image.Image,
        prompt: str,
        *,
        strength: float = 0.22,
        steps: int = 1,
        seed: Optional[int] = None,
        references: Optional[VisualReferenceBundle] = None,
    ) -> RefineResult:
        started = time.perf_counter()
        rgb = image.convert('RGB')
        softened = rgb.filter(ImageFilter.GaussianBlur(radius=0.35))
        rgb = Image.blend(rgb, softened, alpha=0.08)
        rgb = ImageEnhance.Color(rgb).enhance(0.98)
        rgb = ImageEnhance.Contrast(rgb).enhance(1.04)
        rgb = ImageEnhance.Sharpness(rgb).enhance(1.08)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return RefineResult(
            image=rgb,
            backend=self.name,
            duration_ms=duration_ms,
            metadata={
                'strength': strength,
                'steps': steps,
                'generative': False,
                'conditioning_requested': bool(references and references.requested()),
                'conditioning_applied': [],
                'conditioning_note': 'LIGHT CPU não é generativo; referências são registradas, mas não condicionam pixels.',
                'reference_bundle': references.metadata if references else {},
            },
        )


class SdCppImg2ImgRefiner:
    """Generative refinement with capability-aware visual conditioning.

    V0.9 keeps the V0.8 WebUI img2img path as a compatibility fallback. When a
    recent stable-diffusion.cpp server exposes the native API and loaded models
    advertise reference features, identity/pose references are sent through the
    native image fields instead of being represented only in text.
    """

    name = 'sdcpp_img2img'

    def ensure_engine(self) -> tuple[dict[str, Any], int]:
        started = time.perf_counter()
        status = sdcpp_manager.status()
        if not status.get('ready'):
            status = sdcpp_manager.start()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return status, elapsed_ms

    @staticmethod
    def _features(caps: dict[str, Any]) -> dict[str, Any]:
        data = caps.get('data') or {}
        by_mode = data.get('features_by_mode') or {}
        features = by_mode.get('img_gen') or data.get('features') or {}
        if isinstance(features, list):
            return {str(x): True for x in features}
        return features if isinstance(features, dict) else {}

    @staticmethod
    def _enabled(features: dict[str, Any], name: str) -> bool:
        value = features.get(name)
        if isinstance(value, dict):
            return bool(value.get('enabled', True))
        return bool(value)

    def _native_refine(self, image: Image.Image, prompt: str, *, strength: float, steps: int,
                       seed: Optional[int], references: VisualReferenceBundle) -> RefineResult:
        caps = sdcpp_manager.capabilities(timeout=1.2)
        if not caps.get('available'):
            raise RuntimeError(f"API nativa sdcpp indisponível: {caps.get('error')}")
        features = self._features(caps)
        applied: list[str] = []
        skipped: list[str] = []
        ref_images: list[str] = []

        ip_image = None
        if references.identity_image is not None:
            if self._enabled(features, 'ip_adapter_image'):
                ip_image = image_to_base64_png(references.identity_image)
                applied.append('identity:ip_adapter_image')
            else:
                # `ref_images` is a generic model-dependent field. V0.9 does not
                # relabel it as identity preservation without an IP-Adapter path.
                skipped.append('identity:no_ip_adapter_feature')

        control_image = None
        if references.control_image is not None:
            if self._enabled(features, 'control_image'):
                control_image = image_to_base64_png(references.control_image)
                applied.append('pose:control_image')
            else:
                skipped.append('pose_control:no_supported_feature')
        elif references.pose_image is not None:
            skipped.append('pose_control:not_generated')

        if self._enabled(features, 'ref_images'):
            for extra in references.extra_images[:4]:
                ref_images.append(image_to_base64_png(extra))
            if references.extra_images:
                applied.append(f'extras:ref_images:{min(4, len(references.extra_images))}')

        # If the server has no compatible reference feature loaded, stay on the
        # well-tested V0.8 path rather than pretending visual conditioning worked.
        if not applied:
            raise RuntimeError('Runtime sdcpp não anunciou nenhum condicionamento visual aplicável.')

        payload = {
            'prompt': prompt,
            'negative_prompt': 'text, title, logo, watermark, blurry, distorted, extra limbs, bad anatomy, collage seams',
            'width': image.width,
            'height': image.height,
            'strength': max(0.0, min(float(strength), 1.0)),
            'seed': seed if seed is not None else -1,
            'batch_count': 1,
            'auto_resize_ref_image': True,
            'increase_ref_index': False,
            'control_strength': float(references.metadata.get('pose_strength', 0.82)),
            'ip_adapter_strength': float(references.metadata.get('identity_strength', 0.82)),
            'init_image': image_to_base64_png(image),
            'ref_images': ref_images,
            'mask_image': None,
            'control_image': control_image,
            'ip_adapter_image': ip_image,
            'sample_params': {'sample_steps': max(1, min(int(steps), 12))},
            'output_format': 'png',
            'output_compression': 100,
        }
        submit_url = f"{sdcpp_manager.base_url}/sdcpp/v1/img_gen"
        started = time.perf_counter()
        response = requests.post(submit_url, json=payload, timeout=30)
        response.raise_for_status()
        job = response.json()
        job_id = job.get('id')
        if not job_id:
            raise RuntimeError('sdcpp native não retornou id do job.')
        poll_url = f"{sdcpp_manager.base_url}/sdcpp/v1/jobs/{job_id}"
        deadline = time.time() + 1800
        data: dict[str, Any] = {}
        while time.time() < deadline:
            poll = requests.get(poll_url, timeout=20)
            poll.raise_for_status()
            data = poll.json()
            status = data.get('status')
            if status == 'completed':
                break
            if status in {'failed', 'cancelled'}:
                raise RuntimeError(f"sdcpp native {status}: {data.get('error')}")
            time.sleep(0.25)
        else:
            raise RuntimeError('Tempo esgotado aguardando refinamento nativo sdcpp.')
        images = ((data.get('result') or {}).get('images') or [])
        if not images or not images[0].get('b64_json'):
            raise RuntimeError('sdcpp native concluiu sem imagem.')
        out = decode_base64_image(images[0]['b64_json'])
        duration_ms = int((time.perf_counter() - started) * 1000)
        return RefineResult(
            image=out,
            backend=self.name,
            duration_ms=duration_ms,
            metadata={
                'strength': strength,
                'steps': steps,
                'generative': True,
                'transport': 'sdcpp_native_img_gen',
                'native_job_id': job_id,
                'conditioning_requested': True,
                'conditioning_applied': applied,
                'conditioning_skipped': skipped,
                'reference_bundle': references.metadata,
                'capability_features': features,
            },
        )

    def _legacy_refine(self, image: Image.Image, prompt: str, *, strength: float, steps: int,
                       seed: Optional[int], references: Optional[VisualReferenceBundle], fallback_error: Optional[str] = None) -> RefineResult:
        strength = max(0.0, min(float(strength), 1.0))
        steps = max(1, min(int(steps), 12))
        url = f"{sdcpp_manager.base_url}/sdapi/v1/img2img"
        payload = {
            'prompt': prompt,
            'negative_prompt': 'text, title, logo, watermark, blurry, distorted, extra limbs, bad anatomy, collage seams',
            'init_images': [image_to_base64_png(image)],
            'width': image.width,
            'height': image.height,
            'steps': steps,
            'cfg_scale': 0.0,
            'denoising_strength': strength,
            'seed': seed if seed is not None else -1,
            'batch_size': 1,
        }
        started = time.perf_counter()
        try:
            response = requests.post(url, json=payload, timeout=1800)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f'Falha no refinador SD.CPP em {url}: {exc}') from exc
        images = data.get('images') or []
        if not images:
            raise RuntimeError('O refinador SD.CPP não retornou imagem.')
        out = decode_base64_image(images[0])
        duration_ms = int((time.perf_counter() - started) * 1000)
        return RefineResult(
            image=out,
            backend=self.name,
            duration_ms=duration_ms,
            metadata={
                'strength': strength,
                'steps': steps,
                'generative': True,
                'url': url,
                'transport': 'sdapi_img2img_compat',
                'conditioning_requested': bool(references and references.requested()),
                'conditioning_applied': [],
                'conditioning_fallback': fallback_error,
                'reference_bundle': references.metadata if references else {},
            },
        )

    def refine(
        self,
        image: Image.Image,
        prompt: str,
        *,
        strength: float = 0.24,
        steps: int = 3,
        seed: Optional[int] = None,
        references: Optional[VisualReferenceBundle] = None,
    ) -> RefineResult:
        self.ensure_engine()
        if references and references.requested():
            try:
                return self._native_refine(image, prompt, strength=strength, steps=steps, seed=seed, references=references)
            except Exception as exc:
                # Compatibility is a first-class requirement: old sd-server builds
                # and missing ControlNet/IP-Adapter weights must not break V0.8.
                return self._legacy_refine(
                    image, prompt, strength=strength, steps=steps, seed=seed,
                    references=references, fallback_error=str(exc),
                )
        return self._legacy_refine(image, prompt, strength=strength, steps=steps, seed=seed, references=references)


def build_refiner(name: str):
    key = (name or 'light_cpu').strip().lower()
    if key in {'light', 'light_cpu', 'cpu_light'}:
        return LightRefiner()
    if key in {'sdcpp', 'sdcpp_img2img', 'img2img'}:
        return SdCppImg2ImgRefiner()
    raise ValueError(f'Refinador desconhecido: {name}')
