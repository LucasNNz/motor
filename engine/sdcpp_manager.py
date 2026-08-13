from __future__ import annotations

import atexit
import os
import subprocess
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import requests

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
RUNTIME_DIR = PROJECT_DIR / "runtime" / "sdcpp"
MODELS_DIR = PROJECT_DIR / "models"
DEFAULT_PORT = int(os.environ.get("SDCPP_PORT", "7861"))
DEFAULT_HOST = "127.0.0.1"


@dataclass
class EngineState:
    running: bool = False
    ready: bool = False
    pid: Optional[int] = None
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    exe_path: Optional[str] = None
    model_path: Optional[str] = None
    mode: str = "unknown"
    started_by_app: bool = False
    last_error: Optional[str] = None
    log_path: Optional[str] = None


class StableDiffusionCppManager:
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._log_handle = None
        self._lock = threading.Lock()
        self.state = EngineState()

    @property
    def base_url(self) -> str:
        return f"http://{self.state.host}:{self.state.port}"

    def _detect_executable(self) -> Optional[Path]:
        candidates = [RUNTIME_DIR / "sd-server.exe", RUNTIME_DIR / "sd-server"]
        candidates.extend(RUNTIME_DIR.rglob("sd-server.exe"))
        candidates.extend(RUNTIME_DIR.rglob("sd-server"))
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def _detect_model(self) -> Optional[Path]:
        preferred = MODELS_DIR / "sd_turbo.safetensors"
        if preferred.exists():
            return preferred
        for pattern in ("*.safetensors", "*.gguf", "*.ckpt"):
            matches = sorted(MODELS_DIR.glob(pattern))
            if matches:
                return matches[0]
        return None

    def _detect_mode(self) -> str:
        marker = RUNTIME_DIR / "engine_mode.txt"
        if marker.exists():
            try:
                value = marker.read_text(encoding="utf-8").strip().lower()
                if value:
                    return value
            except Exception:
                pass
        return "auto"

    def probe(self, timeout: float = 1.0) -> bool:
        try:
            response = requests.get(f"{self.base_url}/sdapi/v1/options", timeout=timeout)
            if response.ok:
                self.state.running = True
                self.state.ready = True
                return True
        except Exception:
            pass
        self.state.ready = False
        if self._process is not None:
            self.state.running = self._process.poll() is None
        else:
            self.state.running = False
        return False

    def status(self) -> dict:
        exe = self._detect_executable()
        model = self._detect_model()
        self.state.exe_path = str(exe) if exe else None
        self.state.model_path = str(model) if model else None
        self.state.mode = self._detect_mode()
        self.probe(timeout=0.35)
        data = asdict(self.state)
        data.update({
            "engine_installed": exe is not None,
            "model_installed": model is not None,
            "base_url": self.base_url,
            "runtime_dir": str(RUNTIME_DIR),
            "models_dir": str(MODELS_DIR),
        })
        return data

    def start(self, wait_seconds: int = 600) -> dict:
        with self._lock:
            if self.probe(timeout=0.5):
                self.state.last_error = None
                return self.status()

            exe = self._detect_executable()
            model = self._detect_model()
            if not exe:
                raise RuntimeError(
                    "stable-diffusion.cpp ainda não está instalado. Rode scripts\\setup_windows_vulkan.ps1 (recomendado) ou scripts\\setup_windows_cpu.ps1."
                )
            if not model:
                raise RuntimeError(
                    "Modelo não encontrado. Rode o script de setup ou coloque sd_turbo.safetensors na pasta models."
                )

            self.state.exe_path = str(exe)
            self.state.model_path = str(model)
            self.state.mode = self._detect_mode()
            self.state.last_error = None

            log_path = PROJECT_DIR / "outputs" / "sdcpp-server.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = open(log_path, "a", encoding="utf-8", buffering=1)
            self.state.log_path = str(log_path)

            command = [
                str(exe),
                "--listen-ip", self.state.host,
                "--listen-port", str(self.state.port),
                "-m", str(model),
                "--steps", "1",
                "--cfg-scale", "0.0",
            ]

            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            try:
                self._process = subprocess.Popen(
                    command,
                    cwd=str(exe.parent),
                    stdout=self._log_handle,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                )
            except Exception as exc:
                self.state.last_error = str(exc)
                raise RuntimeError(f"Não foi possível iniciar sd-server: {exc}") from exc

            self.state.running = True
            self.state.started_by_app = True
            self.state.pid = self._process.pid

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if self._process and self._process.poll() is not None:
                self.state.running = False
                self.state.ready = False
                tail = self._read_log_tail()
                self.state.last_error = f"sd-server encerrou durante a inicialização. {tail}"
                raise RuntimeError(self.state.last_error)
            if self.probe(timeout=0.8):
                self.state.last_error = None
                return self.status()
            time.sleep(1.0)

        tail = self._read_log_tail()
        self.state.last_error = f"Tempo esgotado aguardando o motor carregar. {tail}"
        raise RuntimeError(self.state.last_error)

    def stop(self) -> dict:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=8)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
            self._process = None
            if self._log_handle:
                try:
                    self._log_handle.close()
                except Exception:
                    pass
                self._log_handle = None
            self.state.running = False
            self.state.ready = False
            self.state.pid = None
            self.state.started_by_app = False
        return self.status()

    def _read_log_tail(self, max_chars: int = 1800) -> str:
        path = Path(self.state.log_path) if self.state.log_path else None
        if not path or not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return text[-max_chars:].replace("\n", " | ")
        except Exception:
            return ""


manager = StableDiffusionCppManager()
atexit.register(manager.stop)
