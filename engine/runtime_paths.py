from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))

if IS_VERCEL:
    DATA_DIR = Path(os.environ.get("CORVO_DATA_DIR") or "/tmp/corvo-image-engine")
else:
    DATA_DIR = Path(os.environ.get("CORVO_DATA_DIR") or PROJECT_DIR)

OUTPUTS_DIR = DATA_DIR / "outputs"
OPERATIONS_DIR = DATA_DIR / "operations"
LIBRARY_DIR = DATA_DIR / "CORVO_LIBRARY"
BENCHMARKS_DIR = OUTPUTS_DIR / "refiner_benchmarks"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    OPERATIONS_DIR.mkdir(parents=True, exist_ok=True)
    BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)


def seed_mutable_tree(name: str) -> Path:
    """Return a writable tree, copying bundled seed data on ephemeral runtimes."""
    source = PROJECT_DIR / name
    target = DATA_DIR / name
    if source.resolve() == target.resolve():
        target.mkdir(parents=True, exist_ok=True)
        return target
    if not target.exists():
        if source.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.mkdir(parents=True, exist_ok=True)
    return target


def runtime_status() -> dict:
    return {
        "runtime_mode": "vercel" if IS_VERCEL else "local",
        "is_vercel": IS_VERCEL,
        "project_dir": str(PROJECT_DIR),
        "data_dir": str(DATA_DIR),
        "storage": "ephemeral_tmp" if IS_VERCEL else "persistent_local",
        "local_processes_allowed": not IS_VERCEL,
    }


ensure_data_dirs()
