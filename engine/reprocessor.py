from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFilter

from .composer_engine import composer_engine
from .anatomy_locator import anatomy_locator
from .memory_manager import memory_manager
from .refiner import build_refiner
from .reference_conditioning import VisualReferenceBundle


@dataclass
class RegionSelection:
    name: str
    box: tuple[int, int, int, int]  # x, y, w, h in output pixels
    source: str
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        x, y, w, h = self.box
        return {
            'name': self.name,
            'box': [x, y, w, h],
            'source': self.source,
            'confidence': round(float(self.confidence), 3),
        }


class RegionResolver:
    """Resolve named [FIX] regions into image-space boxes.

    Explicit `box=` wins. Named body regions use pose anchors when available.
    Hand/arm regions are deliberately heuristic until a skeleton detector is added.
    """

    def _number(self, raw: Any, total: int) -> float:
        if isinstance(raw, (int, float)):
            value = float(raw)
            if 0.0 <= value <= 1.0:
                return value * total
            return value
        text = str(raw or '').strip().lower()
        if text.endswith('%'):
            try:
                return float(text[:-1]) / 100.0 * total
            except Exception:
                return 0.0
        try:
            value = float(text)
            if 0.0 <= value <= 1.0:
                return value * total
            return value
        except Exception:
            return 0.0

    def _clamp_box(self, box: tuple[float, float, float, float], width: int, height: int) -> tuple[int, int, int, int]:
        x, y, w, h = box
        x = max(0.0, min(float(width - 1), x))
        y = max(0.0, min(float(height - 1), y))
        w = max(1.0, min(float(width) - x, w))
        h = max(1.0, min(float(height) - y, h))
        return int(round(x)), int(round(y)), int(round(w)), int(round(h))

    def _explicit_box(self, raw: Any, width: int, height: int) -> Optional[tuple[int, int, int, int]]:
        if raw is None:
            return None
        values = raw if isinstance(raw, (list, tuple)) else [x.strip() for x in str(raw).split(',')]
        if len(values) != 4:
            return None
        x = self._number(values[0], width)
        y = self._number(values[1], height)
        w = self._number(values[2], width)
        h = self._number(values[3], height)
        return self._clamp_box((x, y, w, h), width, height)

    def _asset_from_plan(self, composition: dict[str, Any], label: str) -> Optional[dict[str, Any]]:
        plan = (composition or {}).get('plan') or {}
        row = plan.get(label) or {}
        item_id = row.get('id')
        if not item_id:
            return None
        if item_id in memory_manager.by_id:
            item = memory_manager.by_id[item_id]
            return {
                'id': item_id,
                'anchors': (item.get('metadata') or {}).get('anchors') or row.get('anchors'),
                'anchor_base': (item.get('metadata') or {}).get('anchor_base', 512),
            }
        return next((a for a in composer_engine.bank.assets if a.get('id') == item_id), None)

    def _anchor_to_pixels(self, raw: Any, width: int, height: int, base: int = 512) -> Optional[tuple[int, int, int, int]]:
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            return None
        try:
            vals = [float(x) for x in raw]
        except Exception:
            return None
        if all(0.0 <= x <= 1.0 for x in vals):
            return self._clamp_box((vals[0] * width, vals[1] * height, vals[2] * width, vals[3] * height), width, height)
        sx = width / float(base or 512)
        sy = height / float(base or 512)
        return self._clamp_box((vals[0] * sx, vals[1] * sy, vals[2] * sx, vals[3] * sy), width, height)

    def resolve(self, fix: dict[str, Any], composition: dict[str, Any], width: int, height: int, image: Optional[Image.Image] = None) -> RegionSelection:
        region = str(fix.get('region') or 'full').strip().lower().replace(' ', '_')
        aliases = {
            'rosto': 'face', 'cabeca': 'head', 'cabeça': 'head',
            'mao_direita': 'right_hand', 'mão_direita': 'right_hand',
            'mao_esquerda': 'left_hand', 'mão_esquerda': 'left_hand',
            'braco_direito': 'right_arm', 'braço_direito': 'right_arm',
            'braco_esquerdo': 'left_arm', 'braço_esquerdo': 'left_arm',
            'perna_direita': 'right_leg', 'perna_esquerda': 'left_leg',
            'tronco': 'torso',
            'personagem': 'character', 'corpo': 'body', 'sujeito': 'character',
            'objeto': 'object', 'imagem': 'full', 'tudo': 'full',
        }
        region = aliases.get(region, region)
        explicit = self._explicit_box(fix.get('box') or fix.get('bbox'), width, height)
        if explicit:
            return RegionSelection(region, explicit, 'fix.box', 1.0)

        # V0.9: real body landmarks win over static anchors when the optional
        # detector is installed and confident. The fallback chain remains intact.
        if image is not None and region in {'head', 'face', 'right_hand', 'left_hand', 'right_arm', 'left_arm', 'right_leg', 'left_leg', 'torso', 'character', 'body'}:
            detected = anatomy_locator.detect(image)
            if detected and region in detected.regions:
                row = detected.regions[region]
                box = tuple(int(x) for x in row.get('box', []))
                if len(box) == 4:
                    return RegionSelection(region, box, 'mediapipe_pose_landmarker', float(row.get('confidence') or detected.confidence))

        pose = self._asset_from_plan(composition, 'pose') or {}
        anchors = pose.get('anchors') or {}
        base = int(pose.get('anchor_base') or 512)
        head = self._anchor_to_pixels(anchors.get('head'), width, height, base)
        character = self._anchor_to_pixels(anchors.get('character_box'), width, height, base)
        obj = self._anchor_to_pixels(anchors.get('object_target'), width, height, base)

        if region in {'head', 'face'} and head:
            return RegionSelection(region, head, 'pose.anchor.head', 0.96)
        if region == 'object' and obj:
            return RegionSelection(region, obj, 'pose.anchor.object_target', 0.93)
        if region in {'character', 'body'} and character:
            return RegionSelection(region, character, 'pose.anchor.character_box', 0.93)

        if character:
            x, y, w, h = character
            # Viewer-relative heuristic until a pose/skeleton detector is available.
            if region == 'right_hand':
                box = (x + w * 0.70, y + h * 0.42, w * 0.34, h * 0.25)
                return RegionSelection(region, self._clamp_box(box, width, height), 'heuristic.character_box', 0.58)
            if region == 'left_hand':
                box = (x - w * 0.04, y + h * 0.42, w * 0.34, h * 0.25)
                return RegionSelection(region, self._clamp_box(box, width, height), 'heuristic.character_box', 0.58)
            if region == 'right_arm':
                box = (x + w * 0.60, y + h * 0.28, w * 0.43, h * 0.42)
                return RegionSelection(region, self._clamp_box(box, width, height), 'heuristic.character_box', 0.55)
            if region == 'left_arm':
                box = (x - w * 0.03, y + h * 0.28, w * 0.43, h * 0.42)
                return RegionSelection(region, self._clamp_box(box, width, height), 'heuristic.character_box', 0.55)

        # Unknown named region: use a conservative central region instead of silently editing the whole image.
        if region not in {'full', 'all'}:
            box = (width * 0.30, height * 0.30, width * 0.40, height * 0.40)
            return RegionSelection(region, self._clamp_box(box, width, height), 'fallback.center', 0.20)
        return RegionSelection('full', (0, 0, width, height), 'full_image', 1.0)


class RegionalReprocessor:
    def __init__(self):
        self.resolver = RegionResolver()

    @staticmethod
    def _ratio(raw: Any, default: float, lo: float = 0.0, hi: float = 1.0) -> float:
        if raw is None:
            return default
        try:
            if isinstance(raw, str) and raw.strip().endswith('%'):
                value = float(raw.strip()[:-1]) / 100.0
            else:
                value = float(raw)
            return max(lo, min(hi, value))
        except Exception:
            return default

    @staticmethod
    def _expand(box: tuple[int, int, int, int], width: int, height: int, margin: float) -> tuple[int, int, int, int]:
        x, y, w, h = box
        dx = w * margin
        dy = h * margin
        x0 = max(0, int(math.floor(x - dx)))
        y0 = max(0, int(math.floor(y - dy)))
        x1 = min(width, int(math.ceil(x + w + dx)))
        y1 = min(height, int(math.ceil(y + h + dy)))
        return x0, y0, max(1, x1 - x0), max(1, y1 - y0)

    @staticmethod
    def _mask_for_target(crop_box: tuple[int, int, int, int], target_box: tuple[int, int, int, int], feather: float) -> Image.Image:
        cx, cy, cw, ch = crop_box
        tx, ty, tw, th = target_box
        mask = Image.new('L', (cw, ch), 0)
        draw = ImageDraw.Draw(mask)
        x0 = max(0, tx - cx)
        y0 = max(0, ty - cy)
        x1 = min(cw, x0 + tw)
        y1 = min(ch, y0 + th)
        draw.rectangle((x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)), fill=255)
        radius = max(1.0, min(tw, th) * feather)
        return mask.filter(ImageFilter.GaussianBlur(radius=radius))

    @staticmethod
    def _prompt(fix: dict[str, Any], reprocess: dict[str, Any], region: RegionSelection) -> str:
        action = str(fix.get('action') or 'redraw')
        problem = str(fix.get('problem') or fix.get('instruction') or '').strip()
        preserve = [k for k, v in (reprocess or {}).items() if k.startswith('preserve_') and bool(v)]
        parts = [
            f'LOCAL REPAIR ONLY: {region.name}',
            f'ACTION: {action}',
            'preserve the surrounding image, identity, pose, perspective, colors and lighting',
            'do not add text, title, logo or watermark',
        ]
        if preserve:
            parts.append('PRESERVE FLAGS: ' + ', '.join(preserve))
        if problem:
            parts.append('PROBLEM TO FIX: ' + problem)
        return '. '.join(parts)

    def apply_fix(self, image: Image.Image, *, fix: dict[str, Any], reprocess: dict[str, Any], composition: dict[str, Any],
                  refiner_name: str, steps: int, strength: float,
                  references: Optional[VisualReferenceBundle] = None) -> tuple[Image.Image, dict[str, Any], Image.Image]:
        image = image.convert('RGB')
        region = self.resolver.resolve(fix, composition, image.width, image.height, image=image)
        margin = self._ratio(fix.get('margin'), 0.28, 0.0, 1.0)
        feather = self._ratio(fix.get('feather'), 0.10, 0.0, 0.45)
        local_strength = self._ratio(fix.get('strength'), strength, 0.0, 1.0)
        local_steps = int(fix.get('steps') or steps)
        crop_box = self._expand(region.box, image.width, image.height, margin)
        x, y, w, h = crop_box
        crop = image.crop((x, y, x + w, y + h))
        prompt = self._prompt(fix, reprocess, region)

        refiner = build_refiner(refiner_name)
        started = time.perf_counter()
        result = refiner.refine(crop, prompt, strength=local_strength, steps=local_steps, references=references)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        refined_crop = result.image.convert('RGB').resize(crop.size, Image.Resampling.LANCZOS)
        mask = self._mask_for_target(crop_box, region.box, feather)
        mixed_crop = Image.composite(refined_crop, crop, mask)
        out = image.copy()
        out.paste(mixed_crop, (x, y))

        log = {
            'fix': fix,
            'region': region.as_dict(),
            'crop_box': [x, y, w, h],
            'margin': margin,
            'feather': feather,
            'strength': local_strength,
            'steps': local_steps,
            'prompt': prompt,
            'backend': result.backend,
            'backend_metadata': result.metadata,
            'duration_ms': result.duration_ms or elapsed_ms,
        }
        return out, log, mask


regional_reprocessor = RegionalReprocessor()
