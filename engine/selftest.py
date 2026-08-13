from __future__ import annotations

import time
from pathlib import Path

from .backend import build_backend

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "selftest"
OUT.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    "UM GARFO COMO ELEMENTO PRINCIPAL, CENTRALIZADO, BEM DESTACADO, FUNDO CLARO E SIMPLES, SEM TEXTO.",
    "UM MENINO NINJA SURPRESO APONTANDO PARA UMA CAIXA EM UMA FLORESTA, ILUSTRAÇÃO 2D LIMPA, SEM TEXTO.",
]


def main():
    backend = build_backend("composer")
    print("CORVO IMAGE ENGINE V0.4 — SELF TEST")
    print("Backend:", backend.name)
    for i, prompt in enumerate(PROMPTS, 1):
        started = time.perf_counter()
        img = backend.generate(prompt, 512, 512, None, 1)
        ms = int((time.perf_counter() - started) * 1000)
        path = OUT / f"teste_{i:02d}.png"
        img.save(path)
        print(f"{i:02d}: {ms} ms -> {path.name}")
        print("    plano:", backend.last_info.get("plan"))
    print("SELF TEST CONCLUÍDO")


if __name__ == "__main__":
    main()
