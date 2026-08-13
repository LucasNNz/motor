from __future__ import annotations

import math

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageEnhance, ImageFilter, ImageChops

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
                "composition_suitability": asset.get("composition_suitability"),
                "visual_metrics": asset.get("visual_metrics"),
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
        mem_item = memory_manager.by_id.get(asset.get("id"))
        if mem_item:
            return memory_manager.path_for(mem_item)
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
        # MVP cutout assist: if the source has no alpha but its four corners are nearly
        # the same color, treat that border color as a removable studio/background color.
        # This makes guided searches such as "objeto isolado em fundo branco" useful
        # without requiring a separate segmentation model.
        alpha_extrema = item.getchannel("A").getextrema()
        if alpha_extrema == (255, 255) and item.width > 12 and item.height > 12:
            rgb_item = item.convert("RGB")
            corners = [
                rgb_item.getpixel((1, 1)), rgb_item.getpixel((rgb_item.width - 2, 1)),
                rgb_item.getpixel((1, rgb_item.height - 2)), rgb_item.getpixel((rgb_item.width - 2, rgb_item.height - 2)),
            ]
            spread = max(max(c[i] for c in corners) - min(c[i] for c in corners) for i in range(3))
            if spread <= 34:
                bg_color = tuple(sum(c[i] for c in corners) // len(corners) for i in range(3))
                diff = ImageChops.difference(rgb_item, Image.new("RGB", rgb_item.size, bg_color))
                r, g, b = diff.split()
                magnitude = ImageChops.lighter(ImageChops.lighter(r, g), b)
                mask = magnitude.point(lambda v: 0 if v < 18 else (255 if v > 52 else int((v - 18) / 34 * 255)))
                mask = mask.filter(ImageFilter.GaussianBlur(radius=0.7))
                item.putalpha(mask)
        # Normalize transparent/studio references around the actual subject. This is
        # essential for guide semantics such as subject_scale=62%: the scale must apply
        # to the object, not to the source photo canvas/margins.
        alpha = item.getchannel('A')
        bbox = alpha.getbbox()
        if bbox:
            left, top, right, bottom = bbox
            bw, bh = max(1, right-left), max(1, bottom-top)
            pad_x = max(1, int(bw * 0.035)); pad_y = max(1, int(bh * 0.035))
            crop_box = (max(0, left-pad_x), max(0, top-pad_y), min(item.width, right+pad_x), min(item.height, bottom+pad_y))
            cropped = item.crop(crop_box)
            if cropped.width > 2 and cropped.height > 2 and cropped.size != item.size:
                item = cropped
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

    @staticmethod
    def _remove_uniform_background(item: Image.Image) -> Image.Image:
        """Create alpha for studio/plain backgrounds using border color; deterministic MVP cutout."""
        item = item.convert('RGBA')
        alpha_extrema = item.getchannel('A').getextrema()
        if alpha_extrema != (255,255) or item.width <= 12 or item.height <= 12:
            return item
        rgb_item = item.convert('RGB')
        corners = [
            rgb_item.getpixel((1,1)), rgb_item.getpixel((rgb_item.width-2,1)),
            rgb_item.getpixel((1,rgb_item.height-2)), rgb_item.getpixel((rgb_item.width-2,rgb_item.height-2)),
        ]
        spread = max(max(c[i] for c in corners)-min(c[i] for c in corners) for i in range(3))
        if spread > 34:
            return item
        bg_color = tuple(sum(c[i] for c in corners)//len(corners) for i in range(3))
        diff = ImageChops.difference(rgb_item, Image.new('RGB', rgb_item.size, bg_color))
        r,g,b = diff.split()
        magnitude = ImageChops.lighter(ImageChops.lighter(r,g),b)
        mask = magnitude.point(lambda v: 0 if v < 18 else (255 if v > 52 else int((v-18)/34*255)))
        mask = mask.filter(ImageFilter.GaussianBlur(radius=0.7))
        item.putalpha(mask)
        return item

    @staticmethod
    def _crop_alpha_subject(item: Image.Image, pad_ratio: float = 0.035, alpha_threshold: int = 56) -> Image.Image:
        """Crop around the real foreground, ignoring faint alpha halos/noise.

        Using ``alpha.getbbox()`` directly treats even alpha=1 as subject. After a
        background-removal blur that can leave a nearly full-canvas halo, causing
        subject_scale to resize the old photo canvas instead of the object.
        """
        item = item.convert("RGBA")
        alpha = item.getchannel("A")
        strong = alpha.point(lambda v: 255 if v >= alpha_threshold else 0)
        bbox = strong.getbbox()
        if not bbox:
            # Fall back to any visible alpha only when there is no strong foreground.
            bbox = alpha.getbbox()
        if not bbox:
            return item
        left, top, right, bottom = bbox
        bw, bh = max(1, right-left), max(1, bottom-top)
        pad_x = max(1, int(bw * pad_ratio)); pad_y = max(1, int(bh * pad_ratio))
        box = (max(0, left-pad_x), max(0, top-pad_y), min(item.width, right+pad_x), min(item.height, bottom+pad_y))
        cropped = item.crop(box)
        return cropped if cropped.width > 2 and cropped.height > 2 else item

    @staticmethod
    def _principal_axis_angle(item: Image.Image) -> float | None:
        """Return major alpha-axis angle in degrees (0=horizontal, 90=vertical)."""
        alpha = item.convert("RGBA").getchannel("A")
        # Downsample for predictable CPU cost on serverless/browser-produced assets.
        scale = min(1.0, 220.0 / max(1, max(alpha.size)))
        if scale < 1.0:
            alpha = alpha.resize((max(8, int(alpha.width*scale)), max(8, int(alpha.height*scale))), Image.Resampling.BILINEAR)
        pts=[]
        pix=alpha.load()
        step=max(1, int(max(alpha.size)/180))
        for y in range(0, alpha.height, step):
            for x in range(0, alpha.width, step):
                if pix[x,y] >= 48:
                    pts.append((x,y))
        if len(pts) < 20:
            return None
        mx=sum(x for x,_ in pts)/len(pts); my=sum(y for _,y in pts)/len(pts)
        cxx=sum((x-mx)*(x-mx) for x,_ in pts)/len(pts)
        cyy=sum((y-my)*(y-my) for _,y in pts)/len(pts)
        cxy=sum((x-mx)*(y-my) for x,y in pts)/len(pts)
        # Major eigenvector angle for 2x2 covariance matrix.
        angle=0.5*math.degrees(math.atan2(2*cxy, cxx-cyy))
        if angle < 0:
            angle += 180.0
        return angle

    @classmethod
    def _orient_subject(cls, item: Image.Image, orientation: str | None) -> tuple[Image.Image, float]:
        wanted = normalize_text(str(orientation or '')).replace(' ', '_')
        if wanted not in {'vertical','portrait','upright','em_pe','horizontal','landscape'}:
            return cls._crop_alpha_subject(item), 0.0
        item = cls._crop_alpha_subject(item)
        angle = cls._principal_axis_angle(item)
        if angle is None:
            return item, 0.0
        target = 90.0 if wanted in {'vertical','portrait','upright','em_pe'} else 0.0
        # PIL rotation and image-coordinate PCA use opposite angular signs.
        delta = angle - target
        while delta > 90: delta -= 180
        while delta < -90: delta += 180
        if abs(delta) < 3.0:
            return item, 0.0
        rotated = item.rotate(delta, expand=True, resample=Image.Resampling.BICUBIC)
        return cls._crop_alpha_subject(rotated), float(delta)

    @staticmethod
    def _simple_background(width: int, height: int, rules: Optional[dict[str, Any]] = None) -> Image.Image:
        rules = rules or {}
        brightness = normalize_text(str(rules.get('brightness') or 'light'))
        # Deterministic plain background for object/quiz scenes. No decorative demo assets.
        if brightness in {'dark','escuro','escura'}:
            color=(34,39,48)
        elif brightness in {'medium','medio','média','media'}:
            color=(226,231,238)
        else:
            color=(248,249,251)
        return Image.new('RGBA', (width,height), (*color,255))

    @staticmethod
    def _fraction(value, default: float) -> float:
        if value is None:
            return default
        semantic = {
            'tiny': 0.24, 'small': 0.38, 'medium': 0.52, 'normal': 0.56,
            'large': 0.70, 'big': 0.70, 'xlarge': 0.82, 'very_large': 0.82,
            'center': 0.50, 'left': 0.30, 'right': 0.70, 'top': 0.30, 'bottom': 0.70,
        }
        key = normalize_text(str(value)).replace(' ', '_')
        if key in semantic:
            return semantic[key]
        try:
            v = float(value)
            if v > 1.0:
                v /= 100.0
            return max(0.0, min(1.5, v))
        except Exception:
            return default

    def _compose_object_only(
        self, plan: Plan, width: int, height: int,
        composition_rules: Optional[dict[str, Any]] = None,
        background_rules: Optional[dict[str, Any]] = None,
        object_rules: Optional[dict[str, Any]] = None,
        subject_rules: Optional[dict[str, Any]] = None,
    ) -> Image.Image:
        rules = composition_rules or {}
        bg_rules = background_rules or {}
        obj_rules = object_rules or {}
        subj_rules = subject_rules or {}
        if plan.background:
            bg = Image.open(self.bank.asset_path(plan.background))
            base = self._fit_background(bg, width, height)
        else:
            base = self._simple_background(width, height, bg_rules)

        if plan.object:
            obj = Image.open(self.bank.asset_path(plan.object)).convert('RGBA')
            obj = self._remove_uniform_background(obj)
            orientation = (
                obj_rules.get('orientation') or obj_rules.get('desired_orientation') or
                subj_rules.get('orientation') or rules.get('subject_orientation') or
                ('vertical' if normalize_text(str(obj_rules.get('desired_view') or obj_rules.get('view') or '')) in {'front','frontal'} else None)
            )
            source_size = [obj.width, obj.height]
            obj, rotated_deg = self._orient_subject(obj, orientation)
            oriented_size = [obj.width, obj.height]

            scale = self._fraction(rules.get('object_scale', rules.get('subject_scale')), 0.62)
            pos = rules.get('subject_position')
            cx = self._fraction(rules.get('object_x', rules.get('subject_x', pos)), 0.50)
            cy = self._fraction(rules.get('object_y', rules.get('subject_y', pos)), 0.50)
            orient_norm = normalize_text(str(orientation or '')).replace(' ', '_')

            # `subject_scale` applies to the subject's main axis, not the canvas short side.
            if orient_norm in {'vertical','portrait','upright','em_pe'}:
                target_h = max(32, int(height * min(scale, 0.86)))
                target_w = max(32, int(width * 0.82))
            elif orient_norm in {'horizontal','landscape'}:
                target_w = max(32, int(width * min(scale, 0.86)))
                target_h = max(32, int(height * 0.52))
            else:
                main = max(32, int(min(width,height) * scale))
                target_w = target_h = main

            # Fit the cropped/oriented subject itself into the requested safe area.
            fit = min(target_w / max(1,obj.width), target_h / max(1,obj.height))
            rw=max(1,int(obj.width*fit)); rh=max(1,int(obj.height*fit))
            obj=obj.resize((rw,rh), Image.Resampling.LANCZOS)
            x=int(width*cx-rw/2); y=int(height*cy-rh/2)
            x=max(0,min(width-rw,x)); y=max(0,min(height-rh,y))

            if bool(rules.get('shadow', True)):
                alpha=obj.getchannel('A')
                shadow=Image.new('RGBA', obj.size, (0,0,0,0))
                sa=alpha.filter(ImageFilter.GaussianBlur(radius=max(1,int(min(obj.size)*0.02))))
                shade=Image.new('RGBA',obj.size,(0,0,0,70)); shade.putalpha(sa.point(lambda v:int(v*0.28)))
                base.alpha_composite(shade,(min(width-rw,x+5),min(height-rh,y+8)))
            base.alpha_composite(obj,(x,y))
            self.last_info.setdefault('composer_geometry', {})
            self.last_info['composer_geometry'] = {
                'orientation_requested': orientation, 'rotation_applied_deg': round(rotated_deg,2),
                'source_subject_px': source_size, 'oriented_subject_px': oriented_size,
                'subject_scale': scale, 'subject_box_px':[x,y,rw,rh], 'center':[cx,cy],
            }
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

    @staticmethod
    def _memory_asset(item: dict[str, Any], category: str) -> dict[str, Any]:
        return {
            'id': item['id'], 'category': item.get('type', category), 'tags': item.get('tags', []),
            'file': item.get('local_path'), 'local_path': item.get('local_path'), 'source': item.get('source', 'library'),
            'quality_score': item.get('quality_score', 0), 'relevance_score': item.get('relevance_score', 0),
            'approved': item.get('status') == 'approved' or bool(item.get('approved')), 'concept': item.get('concept'), 'title': item.get('title'),
            'compatible_pose': item.get('metadata', {}).get('compatible_pose'), 'anchors': item.get('metadata', {}).get('anchors'),
            'composition_suitability': item.get('metadata', {}).get('composition_suitability'),
            'visual_metrics': item.get('metadata', {}).get('visual_metrics'),
        }

    def _guided_asset(self, category: str, terms: str, default_id: Optional[str] = None, allow_candidates: bool = False, reference_id: Optional[str] = None):
        # A reference collected/selected for the current operation must win over the
        # global library ranking. Otherwise a warm Vercel /tmp can resurrect an older
        # candidate and make the guide non-deterministic.
        if reference_id:
            pinned = memory_manager.by_id.get(reference_id)
            if pinned and pinned.get('type') == category and pinned.get('status') != 'rejected' and not pinned.get('blocked'):
                return self._memory_asset(pinned, category)
        # Guided production may use shortlisted candidates immediately for this operation,
        # while keeping their library state auditable as candidates.
        mem = memory_manager.search_best(concept=terms or category, type_name=category, limit=1, approved_only=not allow_candidates)
        if mem:
            return self._memory_asset(mem[0], category)
        asset, confidence = self.bank.best(category, terms, default_id=default_id)
        if confidence <= 0 and default_id is None:
            return None
        return asset

    def plan_from_guide(self, guide, *, allow_candidates: bool = False, reference_overrides: Optional[dict[str, str]] = None) -> tuple[Plan, dict[str, Any]]:
        # `guide` can be ParsedGuide or a plain dictionary produced by it.
        first = guide.first if hasattr(guide, 'first') else lambda name: ((guide.get('sections', {}).get(name.upper()) or [{}])[0])
        scene = first('SCENE') or {}
        comp = first('COMPOSITION') or {}
        reference_overrides = dict(reference_overrides or {})
        searches = {}
        if hasattr(guide, 'search_blocks'):
            for name, block in guide.search_blocks():
                searches.setdefault(name, block)
        else:
            for name, rows in guide.get('sections', {}).items():
                if name.startswith('SEARCH_') and rows:
                    searches[name] = rows[0]

        bg_search_block = searches.get('SEARCH_BACKGROUND', {})
        bg_directive = first('BACKGROUND') or {}
        bg_block = bg_search_block or bg_directive
        pose_block = searches.get('SEARCH_POSE', {})
        face_block = searches.get('SEARCH_FACE', {}) or searches.get('SEARCH_EXPRESSION', {})
        char_block = searches.get('SEARCH_CHARACTER', {})
        cloth_block = searches.get('SEARCH_CLOTHES', {}) or searches.get('SEARCH_OUTFIT', {})
        obj_block = searches.get('SEARCH_OBJECT', {})
        light_search_block = searches.get('SEARCH_LIGHTING', {})
        light_directive = first('LIGHTING') or {}
        light_block = light_search_block or light_directive
        camera_block = searches.get('SEARCH_CAMERA', {})

        bg_terms = self._guide_terms(bg_block.get('query'), bg_block.get('environment'), scene.get('environment'), scene.get('style'))
        pose_terms = self._guide_terms(pose_block.get('query'), pose_block.get('pose'), pose_block.get('orientation'), pose_block.get('camera'), scene.get('action'), scene.get('camera'))
        face_terms = self._guide_terms(face_block.get('query'), scene.get('emotion'))
        subject_block = first('SUBJECT') or {}
        char_terms = self._guide_terms(char_block.get('query'), char_block.get('reference_target'), scene.get('visual_reference'), scene.get('subject'), subject_block.get('name') if str(subject_block.get('type') or '').lower() in {'character','personagem','person'} else None)
        cloth_terms = self._guide_terms(cloth_block.get('query'), cloth_block.get('style'), char_terms)
        obj_terms = self._guide_terms(obj_block.get('query'), obj_block.get('object'), scene.get('object'), subject_block.get('name') if str(subject_block.get('type') or '').lower() in {'object','objeto'} else None)

        has_character = bool(
            char_block or scene.get('visual_reference') or scene.get('character') or pose_terms
            or str(scene.get('subject_type') or '').lower() in {'character', 'personagem', 'person'}
            or str(subject_block.get('type') or '').lower() in {'character', 'personagem', 'person'}
        )
        background = self._guided_asset('background', bg_terms, allow_candidates=allow_candidates, reference_id=reference_overrides.get('background')) if bg_search_block else None
        pose = self._guided_asset('pose', pose_terms, default_id='pose_standing_center', allow_candidates=allow_candidates, reference_id=reference_overrides.get('pose')) if has_character else None
        face = self._guided_asset('face', face_terms, default_id='face_neutral', allow_candidates=allow_candidates, reference_id=reference_overrides.get('face')) if has_character else None
        outfit = self._guided_asset('outfit', cloth_terms or char_terms, allow_candidates=allow_candidates, reference_id=reference_overrides.get('outfit')) if has_character else None
        obj = self._guided_asset('object', obj_terms, allow_candidates=allow_candidates, reference_id=reference_overrides.get('object')) if obj_terms else None
        confs = [0.7 if x else 0 for x in [background, pose, face, outfit, obj] if x is not None]
        plan = Plan(
            prompt='[GUIDED_EXECUTION]', normalized_prompt='guided_execution', background=background, pose=pose,
            face=face, outfit=outfit, object=obj, style=str(scene.get('style') or '2d_clean'),
            mode='character_scene' if has_character else 'object_only', confidence=sum(confs)/len(confs) if confs else 0.0,
        )
        extra = {
            'scene': scene, 'composition_rules': comp, 'searches': searches, 'allow_candidates': allow_candidates, 'reference_overrides': reference_overrides,
            'lighting_request': light_block, 'background_request': bg_directive, 'style_request': first('STYLE') or {}, 'camera_request': camera_block,
            'object_request': obj_block, 'subject_request': subject_block,
            'selected': {
                'background': background.get('id') if background else None,
                'pose': pose.get('id') if pose else None,
                'face': face.get('id') if face else None,
                'outfit': outfit.get('id') if outfit else None,
                'object': obj.get('id') if obj else None,
            },
        }
        return plan, extra

    def generate_guided(self, guide, width: int, height: int, *, allow_candidates: bool = False, reference_overrides: Optional[dict[str, str]] = None) -> Image.Image:
        self.bank.reload()
        plan, extra = self.plan_from_guide(guide, allow_candidates=allow_candidates, reference_overrides=reference_overrides)
        if plan.mode == 'character_scene':
            image = self._compose_character_scene(plan, width, height)
        else:
            image = self._compose_object_only(
                plan, width, height, extra.get('composition_rules'), extra.get('background_request'),
                extra.get('object_request'), extra.get('subject_request')
            )
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
        light_type = normalize_text(str(light.get('type') or ''))
        contrast = normalize_text(str(light.get('contrast') or ''))
        if light_type in {'soft', 'suave'}:
            rgb = ImageEnhance.Contrast(rgb).enhance(0.98)
            rgb = ImageEnhance.Brightness(rgb).enhance(1.015)
        elif light_type in {'hard', 'dramatic', 'dura', 'forte'}:
            rgb = ImageEnhance.Contrast(rgb).enhance(1.08)
        if contrast in {'low', 'baixo', 'baixa'}:
            rgb = ImageEnhance.Contrast(rgb).enhance(0.96)
        elif contrast in {'high', 'alto', 'alta'}:
            rgb = ImageEnhance.Contrast(rgb).enhance(1.07)
        image = self._harmonize(rgb)
        geometry = dict(self.last_info.get('composer_geometry') or {})
        self.last_info = {'plan': plan.as_dict(), 'guided': extra, 'bank': self.bank.status(), 'refiner': 'off', 'composer_geometry': geometry}
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
