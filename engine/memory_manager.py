from __future__ import annotations

import io
import json
import re
import time
import hashlib
import shutil
import unicodedata
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from .runtime_paths import PROJECT_DIR, DATA_DIR, LIBRARY_DIR, IS_VERCEL, seed_mutable_tree

ROOT = DATA_DIR
MEMORY_ROOT = LIBRARY_DIR
ASSETS_ROOT = MEMORY_ROOT
INDEX_PATH = MEMORY_ROOT / "library_index.json"
LEGACY_ROOT = PROJECT_DIR / "visual_memory"
LEGACY_INDEX = LEGACY_ROOT / "memory_index.json"

CATEGORY_DIRS = {
    "character": "CHARACTERS",
    "pose": "POSES",
    "face": "FACES",
    "expression": "EXPRESSIONS",
    "outfit": "CLOTHES",
    "clothes": "CLOTHES",
    "background": "BACKGROUNDS",
    "object": "OBJECTS",
    "lighting": "LIGHTING",
    "camera": "CAMERA",
    "weather": "WEATHER",
    "texture": "TEXTURES",
    "style": "STYLES",
    "composition": "COMPOSITIONS",
    "other": "OTHER",
}
VALID_STATES = {"candidates", "approved", "rejected"}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", str(value or "").lower())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^a-z0-9\s_-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str) -> str:
    value = normalize_text(value).replace(" ", "_")
    return re.sub(r"[^a-z0-9_.-]+", "_", value) or "item"


def average_hash(img: Image.Image, size: int = 8) -> str:
    gray = img.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels)
    bits = ''.join('1' if px >= avg else '0' for px in pixels)
    return f"{int(bits, 2):0{size * size // 4}x}"


def hamming_distance_hex(a: str, b: str) -> int:
    try:
        return (int(a, 16) ^ int(b, 16)).bit_count()
    except Exception:
        return 9999


class MemoryManager:
    def __init__(self):
        self.root = seed_mutable_tree("CORVO_LIBRARY")
        self.assets_root = self.root
        self.index_path = self.root / "library_index.json"
        self.ensure_dirs()
        self.reload()
        self._migrate_legacy_if_needed()

    def ensure_dirs(self):
        self.root.mkdir(parents=True, exist_ok=True)
        for dirname in sorted(set(CATEGORY_DIRS.values())):
            (self.root / dirname).mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text(json.dumps({
                "version": 2,
                "created_at": time.time(),
                "updated_at": time.time(),
                "items": [],
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    def _migrate_legacy_if_needed(self):
        if self.items or not LEGACY_INDEX.exists():
            return
        try:
            legacy = json.loads(LEGACY_INDEX.read_text(encoding="utf-8"))
        except Exception:
            return
        migrated = 0
        for item in legacy.get("items", []):
            old_rel = item.get("local_path")
            if not old_rel:
                continue
            old_path = ROOT / old_rel
            if not old_path.exists():
                continue
            try:
                result = self.add_item_from_image(
                    image_bytes=old_path.read_bytes(),
                    type_name=item.get("type", "other"),
                    concept=item.get("concept") or item.get("title") or "legacy",
                    tags=item.get("tags", []),
                    source=item.get("source", "legacy_visual_memory"),
                    source_url=item.get("source_url"),
                    author=item.get("author"),
                    license_name=item.get("license"),
                    title=item.get("title"),
                    query=item.get("query"),
                    quality_score=float(item.get("quality_score") or 0),
                    relevance_score=float(item.get("relevance_score") or 0),
                    approved=bool(item.get("approved")),
                    metadata=item.get("metadata", {}),
                    status="approved" if item.get("approved") else "candidates",
                )
                migrated += int(bool(result.get("saved")))
            except Exception:
                pass
        if migrated:
            self.reload()

    def reload(self):
        self.data = json.loads(self.index_path.read_text(encoding='utf-8'))
        self.items: list[dict[str, Any]] = self.data.get('items', [])
        self.by_id = {item['id']: item for item in self.items}
        return self.status()

    def save(self):
        self.data['items'] = self.items
        self.data['updated_at'] = time.time()
        self.index_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')

    def _category_name(self, type_name: str) -> str:
        return CATEGORY_DIRS.get(type_name, "OTHER")

    def _concept_root(self, type_name: str, concept: str) -> Path:
        root = self.root / self._category_name(type_name) / slugify(concept)[:80]
        for state in VALID_STATES:
            (root / state).mkdir(parents=True, exist_ok=True)
        return root

    def path_for(self, item: dict[str, Any]) -> Path:
        rel = Path(item.get("local_path") or "")
        return rel if rel.is_absolute() else ROOT / rel

    def _sidecar_path(self, item: dict[str, Any]) -> Path:
        return self.path_for(item).with_suffix('.json')

    def _write_sidecar(self, item: dict[str, Any]):
        path = self._sidecar_path(item)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')

    def _move_state(self, item: dict[str, Any], new_state: str):
        if new_state not in VALID_STATES:
            raise ValueError(f"Estado inválido: {new_state}")
        current_path = self.path_for(item)
        concept_root = self._concept_root(item.get('type', 'other'), item.get('concept', 'item'))
        new_path = concept_root / new_state / current_path.name
        if current_path.exists() and current_path.resolve() != new_path.resolve():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(current_path), str(new_path))
            old_sidecar = current_path.with_suffix('.json')
            if old_sidecar.exists():
                shutil.move(str(old_sidecar), str(new_path.with_suffix('.json')))
        item['status'] = new_state
        item['approved'] = new_state == 'approved'
        item['local_path'] = str(new_path.relative_to(ROOT)).replace('\\', '/')
        self._write_sidecar(item)

    def status(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        states = {"candidates": 0, "approved": 0, "rejected": 0}
        for item in self.items:
            counts[item.get('type', 'other')] = counts.get(item.get('type', 'other'), 0) + 1
            states[item.get('status', 'approved' if item.get('approved') else 'candidates')] = states.get(item.get('status', 'candidates'), 0) + 1
        return {
            'root': str(self.root),
            'index': str(self.index_path),
            'total_items': len(self.items),
            'approved_items': states.get('approved', 0),
            'candidate_items': states.get('candidates', 0),
            'rejected_items': states.get('rejected', 0),
            'categories': counts,
            'states': states,
        }

    def _next_id(self, type_name: str, concept: str) -> str:
        prefix = {
            'object': 'obj', 'background': 'bg', 'pose': 'pose', 'face': 'face',
            'expression': 'expr', 'outfit': 'cloth', 'clothes': 'cloth', 'character': 'char',
            'lighting': 'light', 'camera': 'cam', 'weather': 'weather', 'texture': 'tex',
            'style': 'style', 'composition': 'comp',
        }.get(type_name, 'item')
        base = f"{prefix}_{slugify(concept)[:24]}"
        nums = []
        for item in self.items:
            if item['id'].startswith(base + '_'):
                try: nums.append(int(item['id'].rsplit('_', 1)[1]))
                except Exception: pass
        return f"{base}_{(max(nums) + 1) if nums else 1:04d}"

    def list_items(self, type_name: Optional[str] = None, query: Optional[str] = None, approved_only: bool = False, limit: int = 100, status: Optional[str] = None) -> list[dict[str, Any]]:
        items = self.items
        if type_name:
            items = [x for x in items if x.get('type') == type_name]
        if approved_only:
            items = [x for x in items if x.get('status') == 'approved' or x.get('approved')]
        if status:
            items = [x for x in items if x.get('status', 'approved' if x.get('approved') else 'candidates') == status]
        if query:
            q = normalize_text(query)
            items = [x for x in items if q in normalize_text(x.get('concept', '')) or q in normalize_text(x.get('title', '')) or any(q in normalize_text(t) for t in x.get('tags', []))]
        def score(x):
            success = float(x.get('success_rate') or 0)
            return (x.get('status') == 'approved', bool(x.get('preferred')), success, x.get('quality_score', 0), x.get('relevance_score', 0), x.get('created_at', 0))
        return sorted(items, key=score, reverse=True)[:limit]

    def search_best(self, concept: str, type_name: str, limit: int = 10, approved_only: bool = True) -> list[dict[str, Any]]:
        q = normalize_text(concept)
        candidates = self.list_items(type_name=type_name, approved_only=approved_only, limit=1000)
        scored = []
        for item in candidates:
            if item.get('blocked') or item.get('status') == 'rejected':
                continue
            score = 0.0
            c = normalize_text(item.get('concept', ''))
            if c == q: score += 6.0
            elif q and (q in c or c in q): score += 3.0
            for tag in item.get('tags', []):
                nt = normalize_text(tag)
                if nt == q: score += 2.0
                elif q and (q in nt or nt in q): score += 1.0
            score += float(item.get('quality_score') or 0) * 1.2
            score += float(item.get('relevance_score') or 0) * 1.4
            score += float(item.get('success_rate') or 0) * 1.8
            if item.get('status') == 'approved' or item.get('approved'): score += 0.8
            if item.get('preferred'): score += 2.5
            if score > 0: scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def find_duplicate(self, *, source_url: Optional[str], perceptual_hash: Optional[str], similarity_threshold: float = 0.96) -> Optional[dict[str, Any]]:
        for item in self.items:
            if source_url and item.get('source_url') == source_url:
                return item
        if perceptual_hash:
            for item in self.items:
                existing = item.get('perceptual_hash')
                if existing:
                    similarity = 1.0 - min(hamming_distance_hex(existing, perceptual_hash), 64) / 64.0
                    if similarity >= similarity_threshold:
                        return item
        return None

    def add_item_from_image(self, *, image_bytes: bytes, type_name: str, concept: str, tags: list[str], source: str,
                            source_url: Optional[str], author: Optional[str], license_name: Optional[str], title: Optional[str],
                            query: Optional[str], quality_score: float, relevance_score: float, approved: bool = False,
                            metadata: Optional[dict[str, Any]] = None, status: Optional[str] = None,
                            similarity_threshold: float = 0.96) -> dict[str, Any]:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
        width, height = img.size
        phash = average_hash(img)
        dup = self.find_duplicate(source_url=source_url, perceptual_hash=phash, similarity_threshold=similarity_threshold)
        if dup:
            return {'duplicate_of': dup['id'], 'item': dup, 'saved': False}
        state = status or ('approved' if approved else 'candidates')
        if state not in VALID_STATES: state = 'candidates'
        item_id = self._next_id(type_name, concept)
        concept_root = self._concept_root(type_name, concept)
        local_path = concept_root / state / f'{item_id}.png'
        img.save(local_path, format='PNG')
        item = {
            'id': item_id, 'type': type_name, 'category': type_name, 'concept': concept,
            'tags': sorted({normalize_text(x) for x in (tags or []) if normalize_text(x)}),
            'style': (metadata or {}).get('style'),
            'local_path': str(local_path.relative_to(ROOT)).replace('\\', '/'),
            'source': source, 'source_url': source_url, 'original_url': source_url,
            'author': author, 'license': license_name, 'title': title, 'query': query,
            'quality_score': round(float(quality_score or 0), 4),
            'relevance_score': round(float(relevance_score or 0), 4),
            'status': state, 'approved': state == 'approved', 'preferred': False, 'blocked': False,
            'used_count': 0, 'operations_used': [], 'approved_results': 0, 'rejected_results': 0, 'success_rate': 0.0,
            'created_at': time.time(), 'collected_at': time.time(), 'width': width, 'height': height,
            'perceptual_hash': phash, 'sha1': hashlib.sha1(image_bytes).hexdigest(), 'metadata': metadata or {},
        }
        self.items.append(item); self.by_id[item_id] = item; self._write_sidecar(item); self.save()
        return {'saved': True, 'item': item}

    def set_status(self, item_id: str, status: str) -> dict[str, Any]:
        item = self.by_id.get(item_id)
        if not item: raise KeyError(item_id)
        self._move_state(item, status); self.save(); return item

    def approve_item(self, item_id: str, approved: bool = True) -> dict[str, Any]:
        return self.set_status(item_id, 'approved' if approved else 'rejected')

    def update_item(self, item_id: str, *, tags: Optional[list[str]] = None, preferred: Optional[bool] = None,
                    blocked: Optional[bool] = None, metadata: Optional[dict[str, Any]] = None,
                    type_name: Optional[str] = None, concept: Optional[str] = None) -> dict[str, Any]:
        item = self.by_id.get(item_id)
        if not item: raise KeyError(item_id)
        if tags is not None: item['tags'] = sorted({normalize_text(x) for x in tags if normalize_text(x)})
        if preferred is not None: item['preferred'] = bool(preferred)
        if blocked is not None: item['blocked'] = bool(blocked)
        if metadata is not None: item['metadata'] = {**item.get('metadata', {}), **metadata}
        if type_name or concept:
            old_path = self.path_for(item)
            item['type'] = type_name or item.get('type', 'other')
            item['category'] = item['type']
            item['concept'] = concept or item.get('concept', 'item')
            new_root = self._concept_root(item['type'], item['concept'])
            new_path = new_root / item.get('status', 'candidates') / old_path.name
            if old_path.exists() and old_path.resolve() != new_path.resolve():
                new_path.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(old_path), str(new_path))
                old_sidecar = old_path.with_suffix('.json')
                if old_sidecar.exists(): shutil.move(str(old_sidecar), str(new_path.with_suffix('.json')))
            item['local_path'] = str(new_path.relative_to(ROOT)).replace('\\', '/')
        self._write_sidecar(item); self.save(); return item

    def mark_used(self, item_id: str):
        item = self.by_id.get(item_id)
        if item:
            item['used_count'] = int(item.get('used_count') or 0) + 1
            self._write_sidecar(item); self.save()

    def register_result(self, item_ids: list[str], approved: bool):
        for item_id in item_ids:
            item = self.by_id.get(item_id)
            if not item: continue
            key = 'approved_results' if approved else 'rejected_results'
            item[key] = int(item.get(key) or 0) + 1
            total = int(item.get('approved_results') or 0) + int(item.get('rejected_results') or 0)
            item['success_rate'] = round((int(item.get('approved_results') or 0) / total) if total else 0.0, 4)
            self._write_sidecar(item)
        self.save()

    def register_operation_use(self, item_ids: list[str], operation_id: str):
        for item_id in item_ids:
            item = self.by_id.get(item_id)
            if not item:
                continue
            rows = list(item.get('operations_used') or [])
            if operation_id not in rows:
                rows.append(operation_id)
                item['operations_used'] = rows[-200:]
                self._write_sidecar(item)
        self.save()

    def delete_item(self, item_id: str):
        item = self.by_id.get(item_id)
        if not item:
            raise KeyError(item_id)
        path = self.path_for(item)
        sidecar = path.with_suffix('.json')
        if path.exists(): path.unlink()
        if sidecar.exists(): sidecar.unlink()
        self.items = [x for x in self.items if x.get('id') != item_id]
        self.by_id.pop(item_id, None)
        self.save()
        return {'deleted': True, 'id': item_id}

    def record_search_history(self, *, type_name: str, concept: str, entry: dict[str, Any]):
        root = self._concept_root(type_name, concept)
        path = root / 'search_history.json'
        rows = []
        if path.exists():
            try: rows = json.loads(path.read_text(encoding='utf-8'))
            except Exception: rows = []
        rows.append({**entry, 'date': entry.get('date') or time.time()})
        path.write_text(json.dumps(rows[-500:], ensure_ascii=False, indent=2), encoding='utf-8')


memory_manager = MemoryManager()
