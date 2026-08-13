from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from .anatomy_locator import anatomy_locator
from .composer_engine import composer_engine
from .memory_manager import memory_manager

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class VisualReferenceBundle:
    identity_image: Optional[Image.Image] = None
    pose_image: Optional[Image.Image] = None
    control_image: Optional[Image.Image] = None
    extra_images: list[Image.Image] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def requested(self) -> bool:
        return bool(self.identity_image or self.pose_image or self.control_image or self.extra_images)


class ReferenceConditioningBuilder:
    LABEL_PRIORITY = {
        "identity": ["guide_character", "composer_face", "composer_outfit"],
        "pose": ["guide_pose", "composer_pose"],
    }

    @staticmethod
    def _priority(raw: Any, default: float) -> float:
        if isinstance(raw, bool):
            return 0.82 if raw else 0.0
        if isinstance(raw, (int, float)):
            return max(0.0, min(1.0, float(raw)))
        text = str(raw or '').strip().lower()
        levels = {
            'low': 0.55, 'baixa': 0.55, 'baixo': 0.55,
            'medium': 0.72, 'media': 0.72, 'média': 0.72, 'medio': 0.72,
            'high': 0.90, 'alta': 0.90, 'alto': 0.90,
            'very_high': 1.0, 'max': 1.0, 'maximum': 1.0,
        }
        if text in levels:
            return levels[text]
        try:
            return max(0.0, min(1.0, float(text)))
        except Exception:
            return default

    def _path_for(self, ref: dict[str, Any]) -> Optional[Path]:
        item = memory_manager.by_id.get(ref.get("id"))
        if item:
            path = memory_manager.path_for(item)
            return path if path.exists() else None
        asset = next((a for a in composer_engine.bank.assets if a.get("id") == ref.get("id")), None)
        if asset:
            try:
                path = composer_engine.bank.asset_path(asset)
                return path if path.exists() else None
            except Exception:
                return None
        return None

    def _first_image(self, refs: list[dict[str, Any]], labels: list[str]) -> tuple[Optional[Image.Image], Optional[dict[str, Any]]]:
        by_label = {r.get("label"): r for r in refs}
        for label in labels:
            ref = by_label.get(label)
            if not ref:
                continue
            path = self._path_for(ref)
            if not path:
                continue
            try:
                return Image.open(path).convert("RGB"), {"label": label, "id": ref.get("id"), "path": str(path)}
            except Exception:
                continue
        return None, None

    def build(self, refs: list[dict[str, Any]], *, output_size: tuple[int, int], guide_render: Optional[dict[str, Any]] = None) -> VisualReferenceBundle:
        render = guide_render or {}
        identity, identity_meta = self._first_image(refs, self.LABEL_PRIORITY["identity"])
        pose, pose_meta = self._first_image(refs, self.LABEL_PRIORITY["pose"])

        control = None
        control_meta: dict[str, Any] = {"generated": False}
        if pose is not None:
            control, control_meta = anatomy_locator.render_pose_control(pose, target_size=output_size)

        extras: list[Image.Image] = []
        extra_meta: list[dict[str, Any]] = []
        used_ids = {x.get("id") for x in [identity_meta, pose_meta] if x}
        for ref in refs:
            if ref.get("id") in used_ids:
                continue
            path = self._path_for(ref)
            if not path:
                continue
            try:
                extras.append(Image.open(path).convert("RGB"))
                extra_meta.append({"label": ref.get("label"), "id": ref.get("id"), "path": str(path)})
            except Exception:
                pass
            if len(extras) >= 4:
                break

        identity_strength = self._priority(render.get('preserve_character_reference') or render.get('preserve_character'), 0.82)
        pose_strength = self._priority(render.get('preserve_pose'), 0.82)
        return VisualReferenceBundle(
            identity_image=identity,
            pose_image=pose,
            control_image=control,
            extra_images=extras,
            metadata={
                "identity": identity_meta,
                "pose": pose_meta,
                "pose_control": control_meta,
                "extras": extra_meta,
                "render_priorities": render,
                "identity_strength": identity_strength,
                "pose_strength": pose_strength,
                "anatomy": anatomy_locator.status(),
            },
        )


reference_conditioning_builder = ReferenceConditioningBuilder()
