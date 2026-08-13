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
    'allow_cutout_compatible': True,
    'min_cutout_score': 0.42,
}


class FilterPipeline:
    def __init__(self):
        self.session = requests.Session()
        retry = Retry(total=0, connect=0, read=0, backoff_factor=0.0, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(['GET']))
        self.session.mount('https://', HTTPAdapter(max_retries=retry))
        self.session.mount('http://', HTTPAdapter(max_retries=retry))
        self.headers = {
            'User-Agent': 'CorvoImageEngine/0.12.14 (visual-reference-fetcher)',
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
        source_img = Image.open(io.BytesIO(image_bytes))
        img = source_img.convert('RGBA')
        width, height = img.size
        phash = average_hash(img)
        aspect_ratio = round(width / height, 4) if height else None
        alpha = img.getchannel('A')
        alpha_sample = alpha.resize((96, 96), Image.Resampling.BILINEAR)
        alpha_hist = alpha_sample.histogram()
        alpha_total = float(96 * 96)
        # A PNG can contain an alpha channel without containing a transparent
        # background. The failing marine-species plate had alpha 114..255 over the
        # whole rectangle and was therefore incorrectly treated as a perfect cutout.
        # Only pixels that are actually near-transparent count as transparency.
        transparent_pixel_ratio = sum(alpha_hist[:33]) / alpha_total
        alpha_foreground_ratio = sum(alpha_hist[33:]) / alpha_total
        alpha_mask = alpha_sample.point(lambda v: 255 if v >= 33 else 0)
        alpha_band = 8
        alpha_outer_count = 0
        alpha_outer_area = 0
        alpha_pixels = alpha_mask.load()
        for ay in range(96):
            for ax in range(96):
                if ax < alpha_band or ax >= 96-alpha_band or ay < alpha_band or ay >= 96-alpha_band:
                    alpha_outer_area += 1
                    if alpha_pixels[ax, ay]:
                        alpha_outer_count += 1
        alpha_border_foreground_ratio = alpha_outer_count / float(max(1, alpha_outer_area))
        transparent = bool(
            transparent_pixel_ratio >= 0.002
            and 0.01 <= alpha_foreground_ratio <= 0.88
            and alpha_border_foreground_ratio <= 0.28
        )

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

        # MVP cutout compatibility: the source does not need to arrive as a perfect
        # transparent/studio image. If the outer border behaves like a removable
        # background and there is a meaningful foreground region, the Composer can
        # isolate it deterministically. This is intentionally different from the
        # stricter `isolation_score`.
        corners = [
            sample.getpixel((2, 2)), sample.getpixel((93, 2)),
            sample.getpixel((2, 93)), sample.getpixel((93, 93)),
        ]
        corner_spread = max(max(c[i] for c in corners) - min(c[i] for c in corners) for i in range(3))
        bg_color = tuple(sum(c[i] for c in corners) // len(corners) for i in range(3))
        bg_img = Image.new('RGB', sample.size, bg_color)
        bg_diff = ImageChops.difference(sample, bg_img)
        dr, dg, db = bg_diff.split()
        magnitude = ImageChops.lighter(ImageChops.lighter(dr, dg), db)
        hist = magnitude.histogram()
        foreground_pixels = sum(hist[30:])
        foreground_ratio = foreground_pixels / float(96 * 96)
        # Good cutouts normally have a calm border and a foreground occupying a useful
        # but not near-full-frame area. Highly textured table/room backgrounds receive
        # a low cleanliness/uniformity score and do not pass merely by contrast.
        occupancy_score = 0.0
        if 0.015 <= foreground_ratio <= 0.72:
            center = 0.28
            occupancy_score = max(0.0, 1.0 - abs(foreground_ratio - center) / 0.44)
        corner_agreement = max(0.0, min(1.0, 1.0 - corner_spread / 72.0))
        # Measure how much of the estimated foreground leaks into the outside band.
        # A plain/removable background keeps this near zero; a textured scene tends to
        # light up the border mask even when the four corners happen to be similar.
        mask = magnitude.point(lambda v: 255 if v >= 30 else 0)
        band_px = 8
        outer = Image.new('L', mask.size, 0)
        outer.paste(mask.crop((0, 0, 96, band_px)), (0, 0))
        outer.paste(mask.crop((0, 96-band_px, 96, 96)), (0, 96-band_px))
        outer.paste(mask.crop((0, band_px, band_px, 96-band_px)), (0, band_px))
        outer.paste(mask.crop((96-band_px, band_px, 96, 96-band_px)), (96-band_px, band_px))
        outer_hist = outer.histogram()
        outer_nonzero = sum(outer_hist[1:])
        outer_area = 96*96 - (96-2*band_px)*(96-2*band_px)
        border_foreground_ratio = outer_nonzero / float(max(1, outer_area))
        border_background_score = max(0.0, min(1.0, 1.0 - border_foreground_ratio * 4.5))
        cutout_score = 1.0 if transparent else max(0.0, min(1.0,
            border_uniformity * 0.28 + border_cleanliness * 0.24 + corner_agreement * 0.17 + occupancy_score * 0.15 + border_background_score * 0.16
        ))
        cutout_compatible = bool(transparent or (
            cutout_score >= 0.42 and border_texture <= 5.2 and border_foreground_ratio <= 0.18 and foreground_ratio <= 0.72
        ))

        return {
            'image': img, 'width': width, 'height': height,
            'aspect_ratio': aspect_ratio, 'transparent': transparent,
            'transparent_pixel_ratio': round(transparent_pixel_ratio, 4),
            'alpha_foreground_ratio': round(alpha_foreground_ratio, 4),
            'alpha_border_foreground_ratio': round(alpha_border_foreground_ratio, 4),
            'perceptual_hash': phash,
            'border_uniformity': round(border_uniformity, 4),
            'border_brightness': round(border_brightness, 4),
            'edge_density': round(edge_density, 4),
            'border_texture': round(border_texture, 4),
            'border_cleanliness': round(border_cleanliness, 4),
            'isolation_score': round(isolation_score, 4),
            'cutout_score': round(cutout_score, 4),
            'cutout_compatible': cutout_compatible,
            'foreground_ratio': round(foreground_ratio, 4),
            'corner_spread': int(corner_spread),
            'border_foreground_ratio': round(border_foreground_ratio, 4),
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
        # ``concept`` is what we hoped to find, not evidence that the candidate
        # contains it. Including it here rewarded every result even when its title and
        # tags described a completely different subject.
        text_parts = [normalize_text(title or '')] + [normalize_text(t) for t in tags]
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
        try: out['min_cutout_score'] = min(1.0, max(0.0, float(out.get('min_cutout_score', 0.42))))
        except Exception: out['min_cutout_score'] = 0.42
        for key in ('require_isolated', 'reject_busy_background', 'prefer_light_background', 'allow_cutout_compatible'):
            value = out.get(key)
            if isinstance(value, str):
                out[key] = value.strip().lower() in {'1','true','yes','sim','on'}
            else:
                out[key] = bool(value)
        return out

    def metadata_rejection(self, candidate: dict[str, Any], filters: dict[str, Any]) -> Optional[str]:
        text = normalize_text(' '.join([
            str(candidate.get('title') or ''),
            str(candidate.get('description') or ''),
            ' '.join(str(x) for x in (candidate.get('tags') or [])),
            str(candidate.get('source_url') or ''),
            str(candidate.get('image_url') or ''),
        ]))
        semantic_query = normalize_text(str(filters.get('_semantic_query') or ''))
        semantic_tokens = set(semantic_query.split())
        metadata_tokens = set(text.split())

        # Deterministic sense guard for common quiz objects. Search providers may
        # interpret ambiguous English words in unrelated senses (fork=river branch,
        # road, software, biological branching). A candidate must expose at least one
        # identity alias in its own metadata; the query itself is never evidence.
        identity_aliases = {
            'fork': {'fork', 'forks', 'cutlery', 'utensil', 'silverware', 'tableware', 'tine', 'tines', 'prong', 'prongs'},
            'spoon': {'spoon', 'spoons', 'cutlery', 'utensil', 'silverware', 'tableware'},
            'knife': {'knife', 'knives', 'cutlery', 'utensil', 'silverware', 'tableware'},
            'banana': {'banana', 'bananas'}, 'apple': {'apple', 'apples'},
            'book': {'book', 'books'}, 'car': {'car', 'cars', 'automobile', 'vehicle'},
            'ball': {'ball', 'balls'}, 'box': {'box', 'boxes', 'carton'},
        }
        fork_wrong_senses = {
            'dam', 'river', 'creek', 'stream', 'canyon', 'road', 'trail', 'junction',
            'township', 'southfork', 'northfork', 'eastfork', 'westfork', 'software',
            'github', 'repository', 'bicycle', 'bike', 'species', 'marine', 'sponge',
        }
        for identity, aliases in identity_aliases.items():
            if identity not in semantic_tokens:
                continue
            if identity == 'fork' and metadata_tokens & fork_wrong_senses:
                return 'metadados indicam outro sentido de fork, não o talher'
            if not (metadata_tokens & aliases):
                return f'metadados sem evidência semântica do objeto {identity}'
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
            isolation_ok = float(inspection.get('isolation_score') or 0.0) >= float(cfg.get('min_isolation_score') or 0.70)
            cutout_ok = bool(cfg.get('allow_cutout_compatible')) and bool(inspection.get('cutout_compatible')) and float(inspection.get('cutout_score') or 0.0) >= float(cfg.get('min_cutout_score') or 0.42)
            if not isolation_ok and not cutout_ok:
                return False, (
                    f"referência não isolada/recortável "
                    f"(isolation={float(inspection.get('isolation_score') or 0):.2f}, "
                    f"cutout={float(inspection.get('cutout_score') or 0):.2f})"
                )
        if cfg.get('reject_busy_background'):
            # A cutout-compatible source may have visible background detail in the
            # original photo, but the Composer can remove it safely. Only reject busy
            # backgrounds when the cutout test also failed.
            if not inspection.get('cutout_compatible'):
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
