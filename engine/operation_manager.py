from __future__ import annotations

import json
import shutil
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
OPERATIONS_ROOT = ROOT / "operations"
OPERATIONS_ROOT.mkdir(parents=True, exist_ok=True)


class OperationManager:
    def new_id(self) -> str:
        return f"operacao_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    def root_for(self, operation_id: str) -> Path:
        return OPERATIONS_ROOT / Path(operation_id).name

    def create(self, *, prompt: str, guide_text: str = "", operation_id: Optional[str] = None,
               parent_operation_id: Optional[str] = None, kind: str = "generation") -> str:
        operation_id = operation_id or self.new_id()
        root = self.root_for(operation_id)
        (root / "etapas").mkdir(parents=True, exist_ok=True)
        (root / "referencias_usadas").mkdir(parents=True, exist_ok=True)
        (root / "logs").mkdir(parents=True, exist_ok=True)
        (root / "pedido_original.txt").write_text(prompt or "", encoding="utf-8")
        (root / "guia_auxiliar.txt").write_text(guide_text or "", encoding="utf-8")
        self.write_json(operation_id, "logs/operacao.json", {
            "operation_id": operation_id,
            "created_at": time.time(),
            "status": "running",
            "kind": kind,
            "parent_operation_id": parent_operation_id,
            "children": [],
        })
        if parent_operation_id:
            self._register_child(parent_operation_id, operation_id)
        return operation_id

    def _register_child(self, parent_operation_id: str, child_operation_id: str):
        path = self.root_for(parent_operation_id) / "logs" / "operacao.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        children = list(data.get("children") or [])
        if child_operation_id not in children:
            children.append(child_operation_id)
        data["children"] = children[-100:]
        self.write_json(parent_operation_id, "logs/operacao.json", data)

    def read_json(self, operation_id: str, rel: str, default: Any = None):
        path = self.root_for(operation_id) / rel
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def read_text(self, operation_id: str, rel: str, default: str = "") -> str:
        path = self.root_for(operation_id) / rel
        if not path.exists():
            return default
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return default

    def copy_parent_references(self, parent_operation_id: str, child_operation_id: str):
        src = self.root_for(parent_operation_id) / "referencias_usadas"
        dst = self.root_for(child_operation_id) / "referencias_usadas"
        copied = []
        if src.exists():
            for path in src.iterdir():
                if not path.is_file():
                    continue
                target = dst / path.name
                shutil.copy2(path, target)
                copied.append(str(target.relative_to(self.root_for(child_operation_id))).replace("\\", "/"))
        return copied

    def write_json(self, operation_id: str, rel: str, data: Any):
        path = self.root_for(operation_id) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_image(self, operation_id: str, rel: str, image):
        path = self.root_for(operation_id) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, format="PNG")
        return path

    def copy_reference(self, operation_id: str, source_path: Path, label: str) -> Optional[str]:
        if not source_path.exists():
            return None
        ext = source_path.suffix or ".png"
        safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in label)[:80]
        target = self.root_for(operation_id) / "referencias_usadas" / f"{safe}{ext}"
        shutil.copy2(source_path, target)
        return str(target.relative_to(self.root_for(operation_id))).replace("\\", "/")

    def finish(self, operation_id: str, *, status: str = "done", diagnostic: str = ""):
        op_path = self.root_for(operation_id) / "logs" / "operacao.json"
        data = json.loads(op_path.read_text(encoding="utf-8")) if op_path.exists() else {"operation_id": operation_id}
        data.update({"status": status, "finished_at": time.time()})
        self.write_json(operation_id, "logs/operacao.json", data)
        (self.root_for(operation_id) / "diagnostico.txt").write_text(diagnostic or status, encoding="utf-8")

    def evaluate(self, operation_id: str, data: dict[str, Any]):
        existing_path = self.root_for(operation_id) / "logs" / "avaliacao.json"
        existing = {}
        if existing_path.exists():
            try:
                existing = json.loads(existing_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        existing.update(data)
        existing["updated_at"] = time.time()
        self.write_json(operation_id, "logs/avaliacao.json", existing)
        return existing

    def status(self, operation_id: str) -> dict[str, Any]:
        root = self.root_for(operation_id)
        if not root.exists():
            raise KeyError(operation_id)
        out = {"operation_id": operation_id, "root": str(root)}
        for name in ["operacao", "buscas", "referencias", "composicao", "refinador", "tempos", "erros", "avaliacao"]:
            path = root / "logs" / f"{name}.json"
            if path.exists():
                try:
                    out[name] = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    out[name] = None
        out["has_result"] = (root / "resultado_final.png").exists()
        return out

    def export_zip(self, operation_id: str) -> Path:
        root = self.root_for(operation_id)
        if not root.exists():
            raise KeyError(operation_id)
        zip_path = root / f"{operation_id}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in root.rglob("*"):
                if path.is_file() and path != zip_path:
                    zf.write(path, path.relative_to(root))
        return zip_path


operation_manager = OperationManager()
