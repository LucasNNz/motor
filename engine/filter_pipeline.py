from __future__ import annotations

import io
from typing import Any, Optional

import requests
from PIL import Image

from .memory_manager import average_hash, hamming_distance_hex, normalize_text


DEFAULT_FILTERS = {
    'min_resolution': 192,
    'reject_text': False,
    'reject_logos': False,
    'reject_watermarks': False,
    'remove_duplicates': True,
    'remove_near_duplicates': True,
    'quality_threshold': 0.0,
    'similarity_threshold': 0.96,
}


class FilterPipeline:
    def download_image(self, url: str) -> bytes:
        response = requests.get(url, timeout=120, headers={'User-Agent': 'CorvoImageEngine/0.7'})
        response.raise_for_status()
        return response.content

    def inspect(self, image_bytes: bytes) -> dict[str, Any]:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
        width, height = img.size
        phash = average_hash(img)
        aspect_ratio = round(width / height, 4) if height else None
        alpha = img.getchannel('A')
        transparent = alpha.getbbox() is not None and alpha.getextrema()[0] < 255
        return {
            'image': img, 'width': width, 'height': height,
            'aspect_ratio': aspect_ratio, 'transparent': transparent,
            'perceptual_hash': phash,
        }

    def quality_score(self, width: int, height: int, transparent: bool, title: Optional[str], tags: list[str]) -> float:
        score = 0.0
        px = width * height
        if px >= 1536 * 1536: score += 0.58
        elif px >= 1024 * 1024: score += 0.48
        elif px >= 768 * 768: score += 0.40
        elif px >= 512 * 512: score += 0.30
        elif px >= 256 * 256: score += 0.18
        else: score += 0.05
        if transparent: score += 0.12
        if title and len(title) > 5: score += 0.08
        if tags: score += min(len(tags), 8) * 0.025
        return min(score, 1.0)

    def relevance_score(self, query: str, title: Optional[str], tags: list[str], concept: Optional[str]) -> float:
        q = normalize_text(query)
        text_parts = [normalize_text(title or ''), normalize_text(concept or '')] + [normalize_text(t) for t in tags]
        score = 0.0
        q_words = set(q.split())
        for part in text_parts:
            if not part: continue
            if part == q: score += 0.45
            elif q in part or part in q: score += 0.22
            else:
                overlap = len(q_words & set(part.split()))
                score += overlap * 0.08
        return min(score, 1.0)

    def normalized_filters(self, filters: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        out = dict(DEFAULT_FILTERS)
        for key, value in (filters or {}).items():
            if value is not None: out[key] = value
        try: out['min_resolution'] = max(64, int(out['min_resolution']))
        except Exception: out['min_resolution'] = 192
        try: out['quality_threshold'] = min(1.0, max(0.0, float(out['quality_threshold'])))
        except Exception: out['quality_threshold'] = 0.0
        try: out['similarity_threshold'] = min(1.0, max(0.0, float(out['similarity_threshold'])))
        except Exception: out['similarity_threshold'] = 0.96
        return out

    def metadata_rejection(self, candidate: dict[str, Any], filters: dict[str, Any]) -> Optional[str]:
        text = normalize_text(' '.join([
            str(candidate.get('title') or ''),
            ' '.join(str(x) for x in (candidate.get('tags') or [])),
        ]))
        if filters.get('reject_watermarks') and any(k in text for k in ['watermark', 'marca dagua', 'stock watermark']):
            return 'metadados indicam marca-d\'água'
        if filters.get('reject_logos') and any(k in text for k in [' logo ', 'logotipo', 'brand mark']):
            return 'metadados indicam logo'
        if filters.get('reject_text') and any(k in text for k in ['text overlay', 'with text', 'typography', 'caption']):
            return 'metadados indicam texto sobreposto'
        return None

    def accept(self, inspection: dict[str, Any], *, filters: Optional[dict[str, Any]] = None,
               quality_score: Optional[float] = None, candidate: Optional[dict[str, Any]] = None) -> tuple[bool, str]:
        cfg = self.normalized_filters(filters)
        if inspection['width'] < cfg['min_resolution'] or inspection['height'] < cfg['min_resolution']:
            return False, f"resolução abaixo de {cfg['min_resolution']}px"
        if inspection['width'] < 64 or inspection['height'] < 64:
            return False, 'imagem inválida'
        if candidate:
            reason = self.metadata_rejection(candidate, cfg)
            if reason: return False, reason
        if quality_score is not None and quality_score < cfg['quality_threshold']:
            return False, f"qualidade {quality_score:.2f} abaixo do limiar {cfg['quality_threshold']:.2f}"
        return True, 'ok'

    def similarity(self, a: str, b: str) -> float:
        return 1.0 - min(hamming_distance_hex(a, b), 64) / 64.0

    def is_duplicate_in_batch(self, phash: str, batch_hashes: list[str], similarity_threshold: float = 0.96) -> bool:
        return any(self.similarity(phash, other) >= similarity_threshold for other in batch_hashes)


filter_pipeline = FilterPipeline()
