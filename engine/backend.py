from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
import os
import textwrap
import time
import base64
import io

from PIL import Image, ImageDraw, ImageFont
import requests

from .sdcpp_manager import manager as sdcpp_manager
from .composer_engine import composer_engine


class ImageBackend(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 1) -> Image.Image:
        raise NotImplementedError


def _decode_first_image(data: dict, source: str) -> Image.Image:
    images = data.get("images") or []
    if not images:
        raise RuntimeError(f"{source} não retornou nenhuma imagem.")
    encoded = images[0]
    if "," in encoded and encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded)
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise RuntimeError(f"{source} retornou uma imagem inválida: {exc}") from exc


class ComposerBackend(ImageBackend):
    """Lightweight visual-memory + composition backend. No CUDA required."""

    name = "composer"

    def __init__(self):
        self.last_info = {}

    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 1) -> Image.Image:
        image = composer_engine.generate(prompt, width, height, seed, steps)
        self.last_info = dict(composer_engine.last_info)
        return image


class MockImageBackend(ImageBackend):
    name = "mock"

    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 1) -> Image.Image:
        img = Image.new("RGB", (width, height), (18, 24, 38))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()

        draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=24, outline=(80, 160, 255), width=3, fill=(25, 34, 52))
        draw.text((40, 40), "IMAGE MOTOR MVP", fill=(255, 255, 255), font=font)
        draw.text((40, 60), f"backend: {self.name}", fill=(152, 199, 255), font=font)
        draw.text((40, 80), f"generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", fill=(180, 180, 180), font=font)

        wrapped = textwrap.wrap(prompt, width=max(18, int(width / 22)))
        y = 130
        for line in wrapped[:20]:
            draw.text((40, y), line, fill=(236, 240, 255), font=font)
            y += 18

        draw.line((40, height - 90, width - 40, height - 90), fill=(80, 160, 255), width=2)
        draw.text((40, height - 70), f"size: {width}x{height} | seed: {seed if seed is not None else '-'} | steps: {steps}", fill=(152, 199, 255), font=font)
        draw.text((40, height - 50), "Mock backend: valida interface, fila e ZIP.", fill=(180, 180, 180), font=font)
        return img


class DiffusersBackend(ImageBackend):
    """Embedded Python fallback that also works on CPU.

    This is intentionally based on SD-Turbo because it is designed for very few
    sampling steps. On a machine without CUDA it loads in float32 on CPU.
    """

    name = "diffusers_cpu"

    def __init__(self, model_id: str = "stabilityai/sd-turbo"):
        self.model_id = model_id
        self._pipeline = None
        self._device = "cpu"

    def _load(self):
        if self._pipeline is not None:
            return
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except Exception as exc:
            raise RuntimeError(
                "Backend Diffusers não instalado. Rode scripts\\setup_windows_diffusers_cpu.ps1 para preparar o modo CPU."
            ) from exc

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if self._device == "cuda" else torch.float32
        kwargs = {"torch_dtype": dtype}
        if self._device == "cuda":
            kwargs["variant"] = "fp16"
        self._pipeline = AutoPipelineForText2Image.from_pretrained(self.model_id, **kwargs)
        self._pipeline = self._pipeline.to(self._device)

        # Optional memory helpers. They are safe to skip if unsupported.
        try:
            self._pipeline.enable_attention_slicing()
        except Exception:
            pass

    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 1) -> Image.Image:
        self._load()
        import torch
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self._device).manual_seed(seed)
        steps = max(1, min(int(steps or 1), 4))
        result = self._pipeline(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=0.0,
            generator=generator,
        )
        return result.images[0]


class WebUICompatibleBackend(ImageBackend):
    def __init__(self, base_url: str, name: str, auto_start_sdcpp: bool = False):
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.auto_start_sdcpp = auto_start_sdcpp

    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 1) -> Image.Image:
        if self.auto_start_sdcpp:
            try:
                if not sdcpp_manager.probe(timeout=0.4):
                    sdcpp_manager.start()
                self.base_url = sdcpp_manager.base_url
            except Exception as exc:
                raise RuntimeError(f"Motor local stable-diffusion.cpp não está pronto: {exc}") from exc

        url = f"{self.base_url}/sdapi/v1/txt2img"
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": max(1, int(steps or 1)),
            "cfg_scale": 0.0 if self.auto_start_sdcpp else 7.0,
            "seed": seed if seed is not None else -1,
            "batch_size": 1,
        }
        try:
            response = requests.post(url, json=payload, timeout=900)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"Falha ao gerar via {self.name} em {url}: {exc}") from exc
        return _decode_first_image(data, self.name)


class Automatic1111Backend(WebUICompatibleBackend):
    def __init__(self, base_url: Optional[str] = None):
        super().__init__(
            base_url=(base_url or os.environ.get("A1111_BASE_URL") or "http://127.0.0.1:7860"),
            name="automatic1111",
            auto_start_sdcpp=False,
        )


class StableDiffusionCppBackend(WebUICompatibleBackend):
    def __init__(self):
        super().__init__(
            base_url=sdcpp_manager.base_url,
            name="sdcpp_local",
            auto_start_sdcpp=True,
        )


def build_backend(name: str, engine_url: Optional[str] = None) -> ImageBackend:
    name = (name or "mock").strip().lower()
    if name in {"composer", "composer_engine", "corvo_composer"}:
        return ComposerBackend()
    if name == "mock":
        return MockImageBackend()
    if name in {"sdcpp", "sdcpp_local", "stable-diffusion-cpp"}:
        return StableDiffusionCppBackend()
    if name in {"diffusers", "diffusers_cpu", "embedded"}:
        return DiffusersBackend()
    if name in {"automatic1111", "a1111", "stable-diffusion-webui"}:
        return Automatic1111Backend(base_url=engine_url)
    raise ValueError(f"Backend desconhecido: {name}")
