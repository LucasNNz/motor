from __future__ import annotations

import io
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageStat, ImageFilter, ImageChops

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
    'require_isolated': False,
    'reject_busy_background': False,
    'prefer_light_background': False,
    'min_isolation_score': 0.70,
}


class FilterPipeline:
    def __init__(self):
        self.session = requests.Session()
        retry = Retry(total=0, connect=0, read=0, backoff_factor=0.0, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(['GET']))
        self.session.mount('https://', HTTPAdapter(max_retries=retry))
        self.session.mount('http://', HTTPAdapter(max_retries=retry))
        self.headers = {
            'User-Agent': 'CorvoImageEngine/0.12.3 (visual-reference-fetcher)',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        }

    def download_image(self, url: str) -> bytes:
        response = self.session.get(url, timeout=(2.0, 3.0), headers=self.headers, allow_redirects=True)
        response.raise_for_status()
        if not response.content:
            raise ValueError('download vazio')
        return response.content

    def download_candidate(self, candidate: dict[str, Any], *, max_attempts: int | None = None) -> tuple[bytes, str, list[dict[str, str]]]:
        urls = []
        for value in (candidate.get('download_urls') or []):
            if value and value not in urls:
                urls.append(str(value))
        for value in (candidate.get('thumbnail_url'), candidate.get('image_url')):
            if value and value not in urls:
                urls.append(str(value))
        attempts: list[dict[str, str]] = []
        last_error: Exception | None = None
        if max_attempts is not None:
            urls = urls[:max(1, int(max_attempts))]
        for url in urls:
            try:
                data = self.download_image(url)
                # Decode here so a 200 HTML error page is not accepted as an image.
                Image.open(io.BytesIO(data)).verify()
                return data, url, attempts
            except Exception as exc:
                last_error = exc
                attempts.append({'url': url, 'error': str(exc)[:240]})
        raise RuntimeError(f"nenhum URL da referência pôde ser baixado ({len(urls)} tentativa(s)): {last_error}")

    def inspect(self, image_bytes: bytes) -> dict[str, Any]:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
        width, height = img.size
        phash = average_hash(img)
        aspect_ratio = round(width / height, 4) if height else None
        alpha = img.getchannel('A')
        transparent = alpha.getbbox() is not None and alpha.getextrema()[0] < 255

        # Cheap deterministic composition metrics. They do not try to understand the
        # picture semantically; they only answer questions the guide can explicitly ask,
        # such as "isolated object" and "avoid busy background".
        sample = img.convert('RGB').resize((96, 96), Image.Resampling.BILINEAR)
        band = 10
        border = Image.new('RGB', (96, band * 4))
        border.paste(sample.crop((0, 0, 96, band)), (0, 0))
        border.paste(sample.crop((0, 96-band, 96, 96)), (0, band))
        left = sample.crop((0, band, band, 96-band)).resize((96, band), Image.Resampling.BILINEAR)
        right = sample.crop((96-band, band, 96, 96-band)).resize((96, band), Image.Resampling.BILINEAR)
        border.paste(left, (0, band*2)); border.paste(right, (0, band*3))
        stat = ImageStat.Stat(border)
        avg_std = sum(stat.stddev[:3]) / 3.0
        avg_mean = sum(stat.mean[:3]) / 3.0
        border_uniformity = max(0.0, min(1.0, 1.0 - avg_std / 72.0))
        border_brightness = max(0.0, min(1.0, avg_mean / 255.0))

        gray = sample.convert('L')
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_hist = edges.histogram()
        edge_pixels = sum(edge_hist[36:])
        edge_density = edge_pixels / float(96 * 96)

        # Texture on the outer border is a stronger signal for table/room/photo
        # backgrounds than simple color variance. Compare the border with a blurred
        # version and measure residual detail.
        border_gray = border.convert('L')
        border_soft = border_gray.filter(ImageFilter.GaussianBlur(radius=1.4))
        border_texture = float(ImageStat.Stat(ImageChops.difference(border_gray, border_soft)).mean[0])
        border_cleanliness = max(0.0, min(1.0, 1.0 - border_texture / 8.0))

        # Transparent references are naturally strong isolation candidates. Otherwise,
        # uniform, quiet borders strongly suggest a studio/isolated reference.
        isolation_score = 1.0 if transparent else max(0.0, min(1.0, border_uniformity * 0.48 + border_cleanliness * 0.34 + (1.0 - min(1.0, edge_density * 2.4)) * 0.18))

        return {
            'image': img, 'width': width, 'height': height,
            'aspect_ratio': aspect_ratio, 'transparent': transparent,
            'perceptual_hash': phash,
            'border_uniformity': round(border_uniformity, 4),
            'border_brightness': round(border_brightness, 4),
            'edge_density': round(edge_density, 4),
            'border_texture': round(border_texture, 4),
            'border_cleanliness': round(border_cleanliness, 4),
            'isolation_score': round(isolation_score, 4),
        }

    def quality_score(self, width: int, height: int, transparent: bool, title: Optional[str], tags: list[str]) -> float:
        # Calibrated for the guide semantics: a normal 512px usable reference should
        # live around 0.60 instead of being treated as low quality by construction.
        short = min(int(width or 0), int(height or 0))
        if short >= 1536: score = 0.76
        elif short >= 1024: score = 0.70
        elif short >= 768: score = 0.64
        elif short >= 512: score = 0.56
        elif short >= 384: score = 0.48
        elif short >= 256: score = 0.38
        else: score = 0.18
        if transparent: score += 0.05
        if title and len(str(title).strip()) > 5: score += 0.05
        if tags: score += min(len(tags), 6) * 0.02
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
        try: out['min_isolation_score'] = min(1.0, max(0.0, float(out.get('min_isolation_score', 0.70))))
        except Exception: out['min_isolation_score'] = 0.70
        for key in ('require_isolated', 'reject_busy_background', 'prefer_light_background'):
            value = out.get(key)
            if isinstance(value, str):
                out[key] = value.strip().lower() in {'1','true','yes','sim','on'}
            else:
                out[key] = bool(value)
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
        if filters.get('require_isolated') and any(k in text for k in ['on table', 'wood table', 'dining table', 'in hand', 'holding fork', 'person holding']):
            return 'metadados incompatíveis com objeto isolado'
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
        if cfg.get('require_isolated') and not inspection.get('transparent'):
            if float(inspection.get('isolation_score') or 0.0) < float(cfg.get('min_isolation_score') or 0.70):
                return False, f"referência não parece isolada (score {float(inspection.get('isolation_score') or 0):.2f})"
        if cfg.get('reject_busy_background'):
            if float(inspection.get('border_texture') or 0.0) > 1.7:
                return False, 'fundo visualmente carregado/texturizado'
            if float(inspection.get('edge_density') or 0.0) > 0.34 and float(inspection.get('border_uniformity') or 0.0) < 0.80:
                return False, 'fundo visualmente carregado'
        if cfg.get('prefer_light_background') and not inspection.get('transparent') and float(inspection.get('border_brightness') or 0.0) < 0.55:
            return False, 'fundo incompatível com preferência clara'
        if quality_score is not None and quality_score < cfg['quality_threshold']:
            return False, f"qualidade {quality_score:.2f} abaixo do limiar {cfg['quality_threshold']:.2f}"
        return True, 'ok'

    def similarity(self, a: str, b: str) -> float:
        return 1.0 - min(hamming_distance_hex(a, b), 64) / 64.0

    def is_duplicate_in_batch(self, phash: str, batch_hashes: list[str], similarity_threshold: float = 0.96) -> bool:
        return any(self.similarity(phash, other) >= similarity_threshold for other in batch_hashes)


filter_pipeline = FilterPipeline()
