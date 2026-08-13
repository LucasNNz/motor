from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageEnhance, ImageFilter

from .seed_visual_bank import build_bank

ROOT = Path(__file__).resolve().parent.parent
BANK_ROOT = ROOT / "visual_bank"
METADATA_PATH = BANK_ROOT / "metadata.json"


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
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
                "file": asset.get("file"),
                "tags": asset.get("tags", []),
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

    def reload(self):
        build_bank(force=False)
        self.data = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        self.assets = self.data.get("assets", [])
        self.by_category: dict[str, list[dict[str, Any]]] = {}
        for asset in self.assets:
            self.by_category.setdefault(asset["category"], []).append(asset)
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "root": str(BANK_ROOT),
            "version": self.data.get("version"),
            "total_assets": len(self.assets),
            "categories": {k: len(v) for k, v in sorted(self.by_category.items())},
            "metadata": str(METADATA_PATH),
        }

    def rebuild_demo(self):
        build_bank(force=True)
        return self.reload()

    def asset_path(self, asset: dict[str, Any]) -> Path:
        return BANK_ROOT / asset["file"]

    def best(self, category: str, prompt: str, required: Optional[dict[str, str]] = None, default_id: Optional[str] = None) -> tuple[Optional[dict[str, Any]], float]:
        candidates = self.by_category.get(category, [])
        if required:
            filtered=[]
            for a in candidates:
                ok=True
                for key,value in required.items():
                    if str(a.get(key)) != str(value):
                        ok=False; break
                if ok: filtered.append(a)
            candidates=filtered
        if not candidates:
            return None, 0.0
        p = normalize_text(prompt)
        words=set(p.split())
        best_asset=None; best_score=-1.0
        for asset in candidates:
            tags=_norm_tags(asset.get("tags", []))
            score=0.0
            for tag in tags:
                if not tag: continue
                if tag in p:
                    score += 4.0 + min(len(tag.split()), 3) * 0.5
                else:
                    tag_words=set(tag.split())
                    overlap=len(words & tag_words)
                    score += overlap * 1.25
            if asset.get("id") == default_id:
                score += 0.4
            if score > best_score:
                best_asset=asset; best_score=score
        confidence = 0.0 if best_score <= 0 else min(1.0, best_score / 8.0)
        return best_asset, confidence


class PromptInterpreter:
    CHARACTER_WORDS = [
        "menino","menina","garoto","garota","pessoa","homem","mulher","crianca","criança",
        "ninja","chef","cozinheiro","personagem","heroi","herói"
    ]

    def __init__(self, bank: VisualBank):
        self.bank=bank

    def interpret(self, prompt: str) -> Plan:
        p=normalize_text(prompt)
        has_character=any(normalize_text(w) in p for w in self.CHARACTER_WORDS)
        object_asset, obj_conf=self.bank.best("object", p)

        # Background defaults to light/simple for quiz images unless a specific scene is present.
        bg_asset, bg_conf=self.bank.best("background", p, default_id="bg_plain_light")
        specific_scene_keywords = ["floresta","mata","cozinha","quarto","escola","cidade","rua","parque","playground","campo","futebol","praia","mar","espaco","espaço","planeta"]
        if not any(normalize_text(x) in p for x in specific_scene_keywords):
            bg_asset = next((a for a in self.bank.by_category.get("background", []) if a.get("id") == "bg_plain_light"), bg_asset)
            bg_conf=max(bg_conf,0.65)

        if not has_character:
            return Plan(
                prompt=prompt,
                normalized_prompt=p,
                background=bg_asset,
                object=object_asset,
                mode="object_only",
                confidence=round((bg_conf + obj_conf) / 2, 3),
            )

        pose_asset, pose_conf=self.bank.best("pose", p, default_id="pose_standing_center")
        if not any(k in p for k in ["apont", "segur", "carreg"]):
            pose_asset = next((a for a in self.bank.by_category.get("pose", []) if a.get("id") == "pose_standing_center"), pose_asset)
            pose_conf=max(pose_conf,0.55)

        face_asset, face_conf=self.bank.best("face", p, default_id="face_neutral")
        if not any(k in p for k in ["surpres", "assust", "espant", "feliz", "sorr", "alegr", "brav", "irrit", "raiva"]):
            face_asset = next((a for a in self.bank.by_category.get("face", []) if a.get("id") == "face_neutral"), face_asset)
            face_conf=max(face_conf,0.55)

        outfit_name="casual"
        if "ninja" in p or "shinobi" in p: outfit_name="ninja"
        elif "chef" in p or "cozinheir" in p: outfit_name="chef"
        outfit_asset=None; outfit_conf=0.0
        if pose_asset:
            required={"compatible_pose": pose_asset["id"]}
            candidates=self.bank.by_category.get("outfit", [])
            outfit_asset=next((a for a in candidates if a.get("compatible_pose")==pose_asset["id"] and f"outfit_{outfit_name}_" in a.get("id","")),None)
            outfit_conf=0.95 if outfit_asset and outfit_name!="casual" else 0.65

        confs=[bg_conf, pose_conf, face_conf, outfit_conf]
        if object_asset: confs.append(obj_conf)
        return Plan(
            prompt=prompt,
            normalized_prompt=p,
            background=bg_asset,
            pose=pose_asset,
            face=face_asset,
            outfit=outfit_asset,
            object=object_asset,
            mode="character_scene",
            confidence=sum(confs)/len(confs) if confs else 0.0,
        )


class ComposerEngine:
    name="composer"

    def __init__(self):
        self.bank=VisualBank()
        self.interpreter=PromptInterpreter(self.bank)
        self.last_info: dict[str, Any] = {}

    def status(self):
        data=self.bank.status()
        data["engine"]="composer"
        data["refiner"]="off"
        data["strategy"]="visual-memory + automatic-composition"
        return data

    def rebuild_demo_bank(self):
        return self.bank.rebuild_demo()

    @staticmethod
    def _fit_background(img: Image.Image, width: int, height: int) -> Image.Image:
        img=img.convert("RGB")
        scale=max(width/img.width,height/img.height)
        nw,nh=int(img.width*scale),int(img.height*scale)
        resized=img.resize((nw,nh),Image.Resampling.LANCZOS)
        left=(nw-width)//2; top=(nh-height)//2
        return resized.crop((left,top,left+width,top+height)).convert("RGBA")

    @staticmethod
    def _paste_full(base: Image.Image, layer: Image.Image):
        layer=layer.convert("RGBA").resize(base.size,Image.Resampling.LANCZOS)
        base.alpha_composite(layer)

    @staticmethod
    def _paste_box(base: Image.Image, layer: Image.Image, box: list[int], base_size: int=512, shadow: bool=True):
        sx=base.width/base_size; sy=base.height/base_size
        x,y,w,h=box
        px,py,pw,ph=int(x*sx),int(y*sy),max(1,int(w*sx)),max(1,int(h*sy))
        item=layer.convert("RGBA")
        scale=min(pw/item.width, ph/item.height)
        target=(max(1,int(item.width*scale)), max(1,int(item.height*scale)))
        item=item.resize(target,Image.Resampling.LANCZOS)
        dx=px+(pw-item.width)//2; dy=py+(ph-item.height)//2
        if shadow:
            alpha=item.getchannel("A")
            sh=Image.new("RGBA",item.size,(0,0,0,0))
            sh.putalpha(alpha.filter(ImageFilter.GaussianBlur(radius=max(1,int(min(item.size)*0.025)))))
            rgb=Image.new("RGBA",item.size,(0,0,0,85)); rgb.putalpha(sh.getchannel("A").point(lambda v:int(v*0.34)))
            base.alpha_composite(rgb,(dx+max(2,int(5*sx)),dy+max(2,int(7*sy))))
        base.alpha_composite(item,(dx,dy))

    def _compose_object_only(self, plan: Plan, width: int, height: int) -> Image.Image:
        bg=Image.open(self.bank.asset_path(plan.background)) if plan.background else Image.new("RGB",(512,512),(245,248,252))
        base=self._fit_background(bg,width,height)
        if plan.object:
            obj=Image.open(self.bank.asset_path(plan.object))
            # Large, centered hero object for quiz readability.
            size=int(min(width,height)*0.62)
            x=(width-size)//2; y=(height-size)//2
            # convert coordinates back to 512 reference so helper scales correctly
            sx=512/width; sy=512/height
            box=[int(x*sx),int(y*sy),int(size*sx),int(size*sy)]
            self._paste_box(base,obj,box,shadow=True)
        return base

    def _compose_character_scene(self, plan: Plan, width: int, height: int) -> Image.Image:
        bg=Image.open(self.bank.asset_path(plan.background)) if plan.background else Image.new("RGB",(512,512),(245,248,252))
        base=self._fit_background(bg,width,height)
        pose=plan.pose
        anchors=(pose or {}).get("anchors",{})
        if pose:
            self._paste_full(base,Image.open(self.bank.asset_path(pose)))
        if plan.outfit:
            self._paste_full(base,Image.open(self.bank.asset_path(plan.outfit)))
        if plan.face and anchors.get("head"):
            self._paste_box(base,Image.open(self.bank.asset_path(plan.face)),anchors["head"],shadow=False)
        if plan.object:
            box=anchors.get("object_target",[350,280,135,135])
            self._paste_box(base,Image.open(self.bank.asset_path(plan.object)),box,shadow=True)
        return base

    @staticmethod
    def _harmonize(img: Image.Image) -> Image.Image:
        # Cheap non-generative refinement: slight color/contrast unification.
        rgb=img.convert("RGB")
        rgb=ImageEnhance.Color(rgb).enhance(0.96)
        rgb=ImageEnhance.Contrast(rgb).enhance(1.035)
        rgb=ImageEnhance.Sharpness(rgb).enhance(1.05)
        return rgb

    def generate(self, prompt: str, width: int, height: int, seed: Optional[int]=None, steps: int=1) -> Image.Image:
        plan=self.interpreter.interpret(prompt)
        if plan.mode=="character_scene":
            image=self._compose_character_scene(plan,width,height)
        else:
            image=self._compose_object_only(plan,width,height)
        image=self._harmonize(image)
        self.last_info={
            "plan":plan.as_dict(),
            "bank":self.bank.status(),
            "refiner":"non-generative-light-harmonization",
        }
        return image


composer_engine = ComposerEngine()
