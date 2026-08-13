from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageEnhance, ImageFilter

from .memory_manager import memory_manager
from .seed_visual_bank import build_bank

ROOT = Path(__file__).resolve().parent.parent
BANK_ROOT = ROOT / "visual_bank"
METADATA_PATH = BANK_ROOT / "metadata.json"


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", str(value or "").lower())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^a-z0-9\s_-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _norm_tags(tags: list[str]) -> list[str]:
    return [normalize_text(x) for x in tags]


@dataclass
class Plan:
    prompt: str
    normalized_prompt: str
    background: Optional[dict[str, Any]] = None
    pose: Optional[dict[str, Any]] = None
    face: Optional[dict[str, Any]] = None
    outfit: Optional[dict[str, Any]] = None
    object: Optional[dict[str, Any]] = None
    style: str = "2d_clean"
    mode: str = "object_only"
    confidence: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        def compact(asset):
            if not asset:
                return None
            return {
                "id": asset.get("id"),
                "file": asset.get("file") or asset.get("local_path"),
                "tags": asset.get("tags", []),
                "source": asset.get("source", "demo"),
                "concept": asset.get("concept"),
                "title": asset.get("title"),
                "anchors": asset.get("anchors"),
            }
        return {
            "mode": self.mode,
            "style": self.style,
            "confidence": round(self.confidence, 3),
            "background": compact(self.background),
            "pose": compact(self.pose),
            "face": compact(self.face),
            "outfit": compact(self.outfit),
            "object": compact(self.object),
        }


class VisualBank:
    def __init__(self):
        self.reload()

    def _demo_assets(self) -> list[dict[str, Any]]:
        build_bank(force=False)
        self.data = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        assets = list(self.data.get("assets", []))
        for asset in assets:
            asset.setdefault('source', 'demo_bank')
        return assets

    def _memory_assets(self) -> list[dict[str, Any]]:
        memory_manager.reload()
        assets = []
        for item in memory_manager.items:
            if item.get('status') != 'approved' or item.get('blocked'):
                continue
            assets.append({
                'id': item['id'],
                'category': item.get('type', 'other'),
                'tags': item.get('tags', []),
                'file': item.get('local_path'),
                'local_path': item.get('local_path'),
                'source': item.get('source', 'memory'),
                'quality_score': item.get('quality_score', 0),
                'relevance_score': item.get('relevance_score', 0),
                'approved': item.get('approved', False),
                'width': item.get('width'),
                'height': item.get('height'),
                'title': item.get('title'),
                'concept': item.get('concept'),
                'license': item.get('license'),
                'author': item.get('author'),
                'compatible_pose': item.get('metadata', {}).get('compatible_pose'),
                'anchors': item.get('metadata', {}).get('anchors'),
            })
        return assets

    def reload(self):
        demo_assets = self._demo_assets()
        memory_assets = self._memory_assets()
        self.assets = demo_assets + memory_assets
        self.by_category: dict[str, list[dict[str, Any]]] = {}
        for asset in self.assets:
            self.by_category.setdefault(asset["category"], []).append(asset)
        self.memory_status = memory_manager.status()
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "root": str(BANK_ROOT),
            "version": self.data.get("version"),
            "total_assets": len(self.assets),
            "categories": {k: len(v) for k, v in sorted(self.by_category.items())},
            "metadata": str(METADATA_PATH),
            "memory": self.memory_status,
        }

    def rebuild_demo(self):
        build_bank(force=True)
        return self.reload()

    def asset_path(self, asset: dict[str, Any]) -> Path:
        rel = asset.get("file") or asset.get("local_path")
        if not rel:
            raise FileNotFoundError(f"Asset sem caminho: {asset.get('id')}")
        rel_path = Path(rel)
        if rel_path.is_absolute():
            return rel_path
        # Collected/auditable assets live at project-root paths such as CORVO_LIBRARY/...
        # Demo assets remain relative to visual_bank/.
        rooted = ROOT / rel_path
        if str(rel).startswith(('visual_memory/', 'CORVO_LIBRARY/')) or rooted.exists():
            return rooted
        return BANK_ROOT / rel_path

    def best(self, category: str, prompt: str, required: Optional[dict[str, str]] = None, default_id: Optional[str] = None) -> tuple[Optional[dict[str, Any]], float]:
        candidates = list(self.by_category.get(category, []))
        if required:
            filtered = []
            for a in candidates:
                ok = True
                for key, value in required.items():
                    if str(a.get(key)) != str(value):
                        ok = False
                        break
                if ok:
                    filtered.append(a)
            candidates = filtered
        if not candidates:
            return None, 0.0
        p = normalize_text(prompt)
        words = set(p.split())
        best_asset = None
        best_score = -1.0
        for asset in candidates:
            tags = _norm_tags(asset.get("tags", []))
            score = 0.0
            for tag in tags:
                if not tag:
                    continue
                if tag in p:
                    score += 4.0 + min(len(tag.split()), 3) * 0.5
                else:
                    tag_words = set(tag.split())
                    overlap = len(words & tag_words)
                    score += overlap * 1.25
            concept = normalize_text(asset.get('concept', ''))
            title = normalize_text(asset.get('title', ''))
            for extra in [concept, title]:
                if not extra:
                    continue
                if extra in p:
                    score += 2.2
                else:
                    overlap = len(words & set(extra.split()))
                    score += overlap * 0.8
            if asset.get("id") == default_id:
                score += 0.4
            score += float(asset.get('quality_score') or 0) * 1.25
            score += float(asset.get('relevance_score') or 0) * 1.4
            if asset.get('approved'):
                score += 0.8
            if asset.get('source') and asset.get('source') != 'demo_bank':
                score += 0.25
            if score > best_score:
                best_asset = asset
                best_score = score
        confidence = 0.0 if best_score <= 0 else min(1.0, best_score / 9.5)
        return best_asset, confidence


class PromptInterpreter:
    CHARACTER_WORDS = [
        "menino", "menina", "garoto", "garota", "pessoa", "homem", "mulher", "crianca", "criança",
        "ninja", "chef", "cozinheiro", "personagem", "heroi", "herói"
    ]

    def __init__(self, bank: VisualBank):
        self.bank = bank

    def interpret(self, prompt: str) -> Plan:
        p = normalize_text(prompt)
        has_character = any(normalize_text(w) in p for w in self.CHARACTER_WORDS)
        object_asset, obj_conf = self.bank.best("object", p)

        bg_asset, bg_conf = self.bank.best("background", p, default_id="bg_plain_light")
        specific_scene_keywords = ["floresta", "mata", "cozinha", "quarto", "escola", "cidade", "rua", "parque", "playground", "campo", "futebol", "praia", "mar", "espaco", "espaço", "planeta"]
        if not any(normalize_text(x) in p for x in specific_scene_keywords):
            bg_asset = next((a for a in self.bank.by_category.get("background", []) if a.get("id") == "bg_plain_light"), bg_asset)
            bg_conf = max(bg_conf, 0.65)

        if not has_character:
            return Plan(
                prompt=prompt,
                normalized_prompt=p,
                background=bg_asset,
                object=object_asset,
                mode="object_only",
                confidence=round((bg_conf + obj_conf) / 2, 3),
            )

        pose_asset, pose_conf = self.bank.best("pose", p, default_id="pose_standing_center")
        if not any(k in p for k in ["apont", "segur", "carreg"]):
            pose_asset = next((a for a in self.bank.by_category.get("pose", []) if a.get("id") == "pose_standing_center"), pose_asset)
            pose_conf = max(pose_conf, 0.55)

        face_asset, face_conf = self.bank.best("face", p, default_id="face_neutral")
        if not any(k in p for k in ["surpres", "assust", "espant", "feliz", "sorr", "alegr", "brav", "irrit", "raiva"]):
            face_asset = next((a for a in self.bank.by_category.get("face", []) if a.get("id") == "face_neutral"), face_asset)
            face_conf = max(face_conf, 0.55)

        outfit_name = "casual"
        if "ninja" in p or "shinobi" in p:
            outfit_name = "ninja"
        elif "chef" in p or "cozinheir" in p:
            outfit_name = "chef"
        outfit_asset = None
        outfit_conf = 0.0
        if pose_asset:
            candidates = self.bank.by_category.get("outfit", [])
            outfit_asset = next((a for a in candidates if a.get("compatible_pose") == pose_asset.get("id") and f"outfit_{outfit_name}_" in a.get("id", "")), None)
            if not outfit_asset:
                outfit_asset, outfit_conf = self.bank.best("outfit", p)
            else:
                outfit_conf = 0.95 if outfit_name != "casual" else 0.65

        confs = [bg_conf, pose_conf, face_conf, outfit_conf]
        if object_asset:
            confs.append(obj_conf)
        return Plan(
            prompt=prompt,
            normalized_prompt=p,
            background=bg_asset,
            pose=pose_asset,
            face=face_asset,
            outfit=outfit_asset,
            object=object_asset,
            mode="character_scene",
            confidence=sum(confs) / len(confs) if confs else 0.0,
        )


class ComposerEngine:
    name = "composer"

    def __init__(self):
        self.bank = VisualBank()
        self.interpreter = PromptInterpreter(self.bank)
        self.last_info: dict[str, Any] = {}

    def status(self):
        data = self.bank.status()
        data["engine"] = "composer"
        data["refiner"] = "off"
        data["strategy"] = "visual-memory + automatic-composition"
        return data

    def rebuild_demo_bank(self):
        return self.bank.rebuild_demo()

    def reload_memory(self):
        return self.bank.reload()

    @staticmethod
    def _fit_background(img: Image.Image, width: int, height: int) -> Image.Image:
        img = img.convert("RGB")
        scale = max(width / img.width, height / img.height)
        nw, nh = int(img.width * scale), int(img.height * scale)
        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        left = (nw - width) // 2
        top = (nh - height) // 2
        return resized.crop((left, top, left + width, top + height)).convert("RGBA")

    @staticmethod
    def _paste_full(base: Image.Image, layer: Image.Image):
        layer = layer.convert("RGBA").resize(base.size, Image.Resampling.LANCZOS)
        base.alpha_composite(layer)

    @staticmethod
    def _paste_box(base: Image.Image, layer: Image.Image, box: list[int], base_size: int = 512, shadow: bool = True):
        sx = base.width / base_size
        sy = base.height / base_size
        x, y, w, h = box
        px, py, pw, ph = int(x * sx), int(y * sy), max(1, int(w * sx)), max(1, int(h * sy))
        item = layer.convert("RGBA")
        scale = min(pw / item.width, ph / item.height)
        target = (max(1, int(item.width * scale)), max(1, int(item.height * scale)))
        item = item.resize(target, Image.Resampling.LANCZOS)
        dx = px + (pw - item.width) // 2
        dy = py + (ph - item.height) // 2
        if shadow:
            alpha = item.getchannel("A")
            sh = Image.new("RGBA", item.size, (0, 0, 0, 0))
            sh.putalpha(alpha.filter(ImageFilter.GaussianBlur(radius=max(1, int(min(item.size) * 0.025)))))
            rgb = Image.new("RGBA", item.size, (0, 0, 0, 85))
            rgb.putalpha(sh.getchannel("A").point(lambda v: int(v * 0.34)))
            base.alpha_composite(rgb, (dx + max(2, int(5 * sx)), dy + max(2, int(7 * sy))))
        base.alpha_composite(item, (dx, dy))

    def _compose_object_only(self, plan: Plan, width: int, height: int) -> Image.Image:
        bg = Image.open(self.bank.asset_path(plan.background)) if plan.background else Image.new("RGB", (512, 512), (245, 248, 252))
        base = self._fit_background(bg, width, height)
        if plan.object:
            obj = Image.open(self.bank.asset_path(plan.object))
            size = int(min(width, height) * 0.62)
            x = (width - size) // 2
            y = (height - size) // 2
            sx = 512 / width
            sy = 512 / height
            box = [int(x * sx), int(y * sy), int(size * sx), int(size * sy)]
            self._paste_box(base, obj, box, shadow=True)
        return base

    def _compose_character_scene(self, plan: Plan, width: int, height: int) -> Image.Image:
        bg = Image.open(self.bank.asset_path(plan.background)) if plan.background else Image.new("RGB", (512, 512), (245, 248, 252))
        base = self._fit_background(bg, width, height)
        pose = plan.pose
        anchors = (pose or {}).get("anchors", {}) or {}
        if pose:
            self._paste_full(base, Image.open(self.bank.asset_path(pose)))
        if plan.outfit:
            self._paste_full(base, Image.open(self.bank.asset_path(plan.outfit)))
        if plan.face and anchors.get("head"):
            self._paste_box(base, Image.open(self.bank.asset_path(plan.face)), anchors["head"], shadow=False)
        if plan.object:
            box = anchors.get("object_target", [350, 280, 135, 135])
            self._paste_box(base, Image.open(self.bank.asset_path(plan.object)), box, shadow=True)
        return base

    @staticmethod
    def _harmonize(img: Image.Image) -> Image.Image:
        rgb = img.convert("RGB")
        rgb = ImageEnhance.Color(rgb).enhance(0.96)
        rgb = ImageEnhance.Contrast(rgb).enhance(1.035)
        rgb = ImageEnhance.Sharpness(rgb).enhance(1.05)
        return rgb


    @staticmethod
    def _guide_terms(*values) -> str:
        parts = []
        for value in values:
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                parts.extend(str(x) for x in value if x is not None)
            elif isinstance(value, dict):
                parts.extend(str(x) for x in value.values() if x is not None)
            else:
                parts.append(str(value))
        return normalize_text(' '.join(parts))

    def _guided_asset(self, category: str, terms: str, default_id: Optional[str] = None):
        # First use the auditable approved library, then fall back to the demo bank.
        mem = memory_manager.search_best(concept=terms or category, type_name=category, limit=1, approved_only=True)
        if mem:
            item = mem[0]
            return {
                'id': item['id'], 'category': item.get('type', category), 'tags': item.get('tags', []),
                'file': item.get('local_path'), 'local_path': item.get('local_path'), 'source': item.get('source', 'library'),
                'quality_score': item.get('quality_score', 0), 'relevance_score': item.get('relevance_score', 0),
                'approved': True, 'concept': item.get('concept'), 'title': item.get('title'),
                'compatible_pose': item.get('metadata', {}).get('compatible_pose'), 'anchors': item.get('metadata', {}).get('anchors'),
            }
        asset, confidence = self.bank.best(category, terms, default_id=default_id)
        if confidence <= 0 and default_id is None:
            return None
        return asset

    def plan_from_guide(self, guide) -> tuple[Plan, dict[str, Any]]:
        # `guide` can be ParsedGuide or a plain dictionary produced by it.
        first = guide.first if hasattr(guide, 'first') else lambda name: ((guide.get('sections', {}).get(name.upper()) or [{}])[0])
        scene = first('SCENE') or {}
        comp = first('COMPOSITION') or {}
        searches = {}
        if hasattr(guide, 'search_blocks'):
            for name, block in guide.search_blocks():
                searches[name] = block
        else:
            for name, rows in guide.get('sections', {}).items():
                if name.startswith('SEARCH_') and rows:
                    searches[name] = rows[0]

        bg_block = searches.get('SEARCH_BACKGROUND', {})
        pose_block = searches.get('SEARCH_POSE', {})
        face_block = searches.get('SEARCH_FACE', {}) or searches.get('SEARCH_EXPRESSION', {})
        char_block = searches.get('SEARCH_CHARACTER', {})
        cloth_block = searches.get('SEARCH_CLOTHES', {}) or searches.get('SEARCH_OUTFIT', {})
        obj_block = searches.get('SEARCH_OBJECT', {})
        light_block = searches.get('SEARCH_LIGHTING', {})
        camera_block = searches.get('SEARCH_CAMERA', {})

        bg_terms = self._guide_terms(bg_block.get('query'), bg_block.get('environment'), scene.get('environment'), scene.get('style'))
        pose_terms = self._guide_terms(pose_block.get('query'), pose_block.get('pose'), pose_block.get('orientation'), pose_block.get('camera'), scene.get('action'), scene.get('camera'))
        face_terms = self._guide_terms(face_block.get('query'), scene.get('emotion'))
        char_terms = self._guide_terms(char_block.get('query'), char_block.get('reference_target'), scene.get('visual_reference'), scene.get('subject'))
        cloth_terms = self._guide_terms(cloth_block.get('query'), cloth_block.get('style'), char_terms)
        obj_terms = self._guide_terms(obj_block.get('query'), obj_block.get('object'), scene.get('object'))

        has_character = bool(char_terms or scene.get('subject') or pose_terms)
        background = self._guided_asset('background', bg_terms, default_id='bg_plain_light')
        pose = self._guided_asset('pose', pose_terms, default_id='pose_standing_center') if has_character else None
        face = self._guided_asset('face', face_terms, default_id='face_neutral') if has_character else None
        outfit = self._guided_asset('outfit', cloth_terms or char_terms) if has_character else None
        obj = self._guided_asset('object', obj_terms) if obj_terms else None
        confs = [0.7 if x else 0 for x in [background, pose, face, outfit, obj] if x is not None]
        plan = Plan(
            prompt='[GUIDED_EXECUTION]', normalized_prompt='guided_execution', background=background, pose=pose,
            face=face, outfit=outfit, object=obj, style=str(scene.get('style') or '2d_clean'),
            mode='character_scene' if has_character else 'object_only', confidence=sum(confs)/len(confs) if confs else 0.0,
        )
        extra = {
            'scene': scene, 'composition_rules': comp, 'searches': searches,
            'lighting_request': light_block, 'camera_request': camera_block,
            'selected': {
                'background': background.get('id') if background else None,
                'pose': pose.get('id') if pose else None,
                'face': face.get('id') if face else None,
                'outfit': outfit.get('id') if outfit else None,
                'object': obj.get('id') if obj else None,
            },
        }
        return plan, extra

    def generate_guided(self, guide, width: int, height: int) -> Image.Image:
        self.bank.reload()
        plan, extra = self.plan_from_guide(guide)
        if plan.mode == 'character_scene':
            image = self._compose_character_scene(plan, width, height)
        else:
            image = self._compose_object_only(plan, width, height)
        # Lightweight deterministic lighting harmonization from the guide.
        light = extra.get('lighting_request') or {}
        temp = normalize_text(str(light.get('temperature') or ''))
        rgb = image.convert('RGB')
        if temp in {'warm', 'quente'}:
            overlay = Image.new('RGB', rgb.size, (255, 225, 185))
            rgb = Image.blend(rgb, overlay, 0.06)
        elif temp in {'cool', 'cold', 'fria', 'frio'}:
            overlay = Image.new('RGB', rgb.size, (195, 220, 255))
            rgb = Image.blend(rgb, overlay, 0.06)
        image = self._harmonize(rgb)
        self.last_info = {'plan': plan.as_dict(), 'guided': extra, 'bank': self.bank.status(), 'refiner': 'off'}
        for asset in [plan.background, plan.pose, plan.face, plan.outfit, plan.object]:
            if asset and asset.get('source') and asset.get('source') != 'demo_bank' and memory_manager.by_id.get(asset.get('id')):
                memory_manager.mark_used(asset['id'])
        return image

    def generate(self, prompt: str, width: int, height: int, seed: Optional[int] = None, steps: int = 1) -> Image.Image:
        self.bank.reload()
        plan = self.interpreter.interpret(prompt)
        if plan.mode == "character_scene":
            image = self._compose_character_scene(plan, width, height)
        else:
            image = self._compose_object_only(plan, width, height)
        image = self._harmonize(image)
        self.last_info = {
            "plan": plan.as_dict(),
            "bank": self.bank.status(),
            "refiner": "non-generative-light-harmonization",
        }
        for asset in [plan.background, plan.pose, plan.face, plan.outfit, plan.object]:
            if asset and asset.get('source') and asset.get('source') != 'demo_bank':
                memory_manager.mark_used(asset['id'])
        return image


composer_engine = ComposerEngine()
