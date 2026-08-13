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


class ImageBackend(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 4) -> Image.Image:
        raise NotImplementedError


class MockImageBackend(ImageBackend):
    name = "mock"

    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 4) -> Image.Image:
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
        draw.text((40, height - 50), "Mock backend: validate UX, queue, ZIP and persistence before the real engine.", fill=(180, 180, 180), font=font)
        return img


class DiffusersBackend(ImageBackend):
    name = "diffusers"

    def __init__(self, model_id: str = "stabilityai/sdxl-turbo"):
        self.model_id = model_id
        self._pipeline = None

    def _load(self):
        if self._pipeline is not None:
            return
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except Exception as exc:
            raise RuntimeError(
                "Diffusers backend is not available in this environment yet. Install 'diffusers', 'transformers' and 'accelerate', then configure a local model."
            ) from exc

        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self._pipeline = AutoPipelineForText2Image.from_pretrained(self.model_id, torch_dtype=dtype)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._pipeline = self._pipeline.to(device)

    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 4) -> Image.Image:
        self._load()
        import torch
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self._pipeline.device).manual_seed(seed)
        result = self._pipeline(prompt=prompt, width=width, height=height, num_inference_steps=steps, generator=generator)
        return result.images[0]


class Automatic1111Backend(ImageBackend):
    name = "automatic1111"

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.environ.get("A1111_BASE_URL") or "http://127.0.0.1:7860").rstrip("/")

    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 4) -> Image.Image:
        url = f"{self.base_url}/sdapi/v1/txt2img"
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "seed": seed if seed is not None else -1,
            "batch_size": 1,
            "n_iter": 1,
        }
        try:
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"Automatic1111 request failed at {url}: {exc}") from exc

        images = data.get("images") or []
        if not images:
            raise RuntimeError("Automatic1111 returned no images.")
        encoded = images[0]
        if "," in encoded and encoded.startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        raw = base64.b64decode(encoded)
        return Image.open(io.BytesIO(raw)).convert("RGB")


def build_backend(name: str, engine_url: Optional[str] = None) -> ImageBackend:
    name = (name or "mock").strip().lower()
    if name == "mock":
        return MockImageBackend()
    if name == "diffusers":
        return DiffusersBackend()
    if name in {"automatic1111", "a1111", "stable-diffusion-webui"}:
        return Automatic1111Backend(base_url=engine_url)
    raise ValueError(f"Unknown backend: {name}")
