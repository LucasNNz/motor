from __future__ import annotations

import math
import time
from typing import Any, Optional

from .filter_pipeline import filter_pipeline
from .memory_manager import memory_manager
from .providers import OpenverseProvider, WikimediaCommonsProvider


class CollectorService:
    def __init__(self):
        self.providers = {'openverse': OpenverseProvider(), 'wikimedia_commons': WikimediaCommonsProvider()}

    def provider_names(self) -> list[str]:
        return list(self.providers.keys())

    def search_candidates(self, query: str, providers: Optional[list[str]] = None, per_provider: int = 12, collect_limit: Optional[int] = None, provider_options: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        provider_names = providers or self.provider_names()
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        provider_trace: list[dict[str, Any]] = []
        target_each = per_provider
        if collect_limit:
            target_each = max(per_provider, math.ceil(collect_limit / max(1, len(provider_names))))
        for name in provider_names:
            provider = self.providers.get(name)
            if not provider:
                errors.append(f'provider desconhecido: {name}'); continue
            provider_started = time.monotonic()
            try:
                found = provider.search(query, page_size=min(max(1, target_each), 100), options=provider_options or {})
                results.extend(found)
                provider_trace.append({
                    'provider': name, 'status': 'ok', 'found': len(found),
                    'elapsed_ms': int((time.monotonic() - provider_started) * 1000),
                })
            except Exception as exc:
                errors.append(f'{name}: {exc}')
                provider_trace.append({
                    'provider': name, 'status': 'error', 'found': 0, 'error': str(exc),
                    'elapsed_ms': int((time.monotonic() - provider_started) * 1000),
                })
        if collect_limit:
            results = results[:max(1, int(collect_limit))]
        return {'query': query, 'providers': provider_names, 'candidates': results, 'errors': errors, 'provider_trace': provider_trace}

    def collect(self, *, query: str, type_name: str, concept: Optional[str] = None, providers: Optional[list[str]] = None,
                per_provider: int = 12, save_limit: int = 5, auto_approve: bool = False,
                filters: Optional[dict[str, Any]] = None, collect_limit: Optional[int] = None,
                keep_limit: Optional[int] = None, search_metadata: Optional[dict[str, Any]] = None, provider_options: Optional[dict[str, Any]] = None,
                processing_budget_seconds: Optional[float] = None, max_download_attempts: Optional[int] = None,
                stop_when_kept: bool = False) -> dict[str, Any]:
        cfg = filter_pipeline.normalized_filters(filters)
        collect_started = time.monotonic()
        budget_exhausted = False
        candidates_processed = 0
        keep_limit = int(keep_limit if keep_limit is not None else save_limit)
        search = self.search_candidates(query=query, providers=providers, per_provider=per_provider, collect_limit=collect_limit, provider_options=provider_options)
        concept = concept or query
        kept: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        batch_hashes: list[str] = []
        saved_candidates: list[dict[str, Any]] = []
        saved_rejected: list[dict[str, Any]] = []

        for cand in search['candidates']:
            if processing_budget_seconds is not None and (time.monotonic() - collect_started) >= float(processing_budget_seconds):
                budget_exhausted = True
                break
            if stop_when_kept and len(kept) >= max(1, keep_limit):
                break
            candidates_processed += 1
            url = cand.get('image_url') or cand.get('thumbnail_url')
            if not url:
                rejected.append({'candidate': cand, 'reason': 'sem url de imagem'}); continue
            # Metadata dimensions are cheap: do not download obviously undersized files.
            cw, ch = cand.get('width'), cand.get('height')
            try:
                if cw and ch and (int(cw) < cfg['min_resolution'] or int(ch) < cfg['min_resolution']):
                    rejected.append({'candidate': cand, 'reason': f"metadados: resolução abaixo de {cfg['min_resolution']}px"})
                    continue
            except Exception:
                pass
            # Reject a semantically incompatible result before downloading it. This
            # keeps ambiguous provider matches from consuming the fast-MVP budget and
            # leaves more time for illustration/vector fallbacks.
            metadata_reason = filter_pipeline.metadata_rejection(cand, cfg)
            if metadata_reason:
                rejected.append({'candidate': cand, 'reason': metadata_reason})
                continue
            try:
                image_bytes, downloaded_from, download_attempts = filter_pipeline.download_candidate(cand, max_attempts=max_download_attempts)
                inspection = filter_pipeline.inspect(image_bytes)
                qscore = filter_pipeline.quality_score(inspection['width'], inspection['height'], inspection['transparent'], cand.get('title'), cand.get('tags') or [])
                rscore = filter_pipeline.relevance_score(query, cand.get('title'), cand.get('tags') or [], concept)
                ok, reason = filter_pipeline.accept(inspection, filters=cfg, quality_score=qscore, candidate=cand)
                phash = inspection['perceptual_hash']
                if ok and cfg.get('remove_near_duplicates') and filter_pipeline.is_duplicate_in_batch(phash, batch_hashes, cfg['similarity_threshold']):
                    ok, reason = False, 'duplicada/quase duplicada no lote'
                if ok and cfg.get('remove_duplicates') and memory_manager.find_duplicate(source_url=cand.get('source_url'), perceptual_hash=phash, similarity_threshold=cfg['similarity_threshold']):
                    ok, reason = False, 'já existe na biblioteca'

                isolation_ok = float(inspection.get('isolation_score') or 0.0) >= float(cfg.get('min_isolation_score') or 0.70)
                cutout_ok = bool(inspection.get('cutout_compatible')) and float(inspection.get('cutout_score') or 0.0) >= float(cfg.get('min_cutout_score') or 0.42)
                acceptance_mode = 'transparent' if inspection.get('transparent') else ('isolated' if isolation_ok else ('cutout' if cutout_ok else 'none'))
                metadata = {
                    'width': inspection['width'], 'height': inspection['height'], 'aspect_ratio': inspection['aspect_ratio'],
                    'transparent': inspection['transparent'], 'search': search_metadata or {}, 'filter_reason': reason,
                    'downloaded_from': downloaded_from, 'download_attempts': download_attempts,
                    'acceptance_mode': acceptance_mode,
                }
                if not ok:
                    result = memory_manager.add_item_from_image(
                        image_bytes=image_bytes, type_name=type_name, concept=concept,
                        tags=list({*(cand.get('tags') or []), concept, query, type_name}), source=cand.get('provider') or 'unknown',
                        source_url=cand.get('source_url'), author=cand.get('author'), license_name=cand.get('license'),
                        title=cand.get('title'), query=query, quality_score=qscore, relevance_score=rscore,
                        approved=False, status='rejected', metadata=metadata, similarity_threshold=1.01,
                    )
                    if result.get('saved'): saved_rejected.append(result['item'])
                    rejected.append({'candidate': cand, 'reason': reason, 'library_id': result.get('item', {}).get('id')}); continue

                batch_hashes.append(phash)
                # For composition, a reliably removable background is almost as useful
                # as a natively isolated reference. Keep the two metrics separately in
                # logs, but rank by the best compositional path available.
                composition_score = max(float(inspection.get('isolation_score') or 0.0), float(inspection.get('cutout_score') or 0.0) * 0.92)
                if cfg.get('prefer_light_background'):
                    composition_score = min(1.0, composition_score * 0.78 + float(inspection.get('border_brightness') or 0.0) * 0.22)
                metadata['composition_suitability'] = round(composition_score, 4)
                metadata['visual_metrics'] = {
                    'isolation_score': inspection.get('isolation_score'),
                    'cutout_score': inspection.get('cutout_score'),
                    'cutout_compatible': inspection.get('cutout_compatible'),
                    'transparent_pixel_ratio': inspection.get('transparent_pixel_ratio'),
                    'alpha_foreground_ratio': inspection.get('alpha_foreground_ratio'),
                    'alpha_border_foreground_ratio': inspection.get('alpha_border_foreground_ratio'),
                    'foreground_ratio': inspection.get('foreground_ratio'),
                    'border_foreground_ratio': inspection.get('border_foreground_ratio'),
                    'border_uniformity': inspection.get('border_uniformity'),
                    'border_brightness': inspection.get('border_brightness'),
                    'edge_density': inspection.get('edge_density'),
                    'border_texture': inspection.get('border_texture'),
                    'border_cleanliness': inspection.get('border_cleanliness'),
                }
                kept.append({'candidate': cand, 'image_bytes': image_bytes, 'inspection': {k: v for k, v in inspection.items() if k != 'image'},
                             'quality_score': qscore, 'relevance_score': rscore, 'composition_score': composition_score,
                             'combined_score': round(qscore * 0.25 + rscore * 0.35 + composition_score * 0.40, 4), 'metadata': metadata})
            except Exception as exc:
                rejected.append({'candidate': cand, 'reason': str(exc)})

        kept.sort(key=lambda x: (x['combined_score'], x['quality_score'], x['relevance_score']), reverse=True)
        for rank, entry in enumerate(kept, start=1):
            cand = entry['candidate']
            shortlisted = rank <= max(0, keep_limit)
            state = ('approved' if auto_approve else 'candidates') if shortlisted else 'rejected'
            metadata = dict(entry['metadata'])
            metadata['rank'] = rank
            metadata['shortlisted'] = shortlisted
            if not shortlisted:
                metadata['filter_reason'] = 'fora do keep_limit após ranking'
            result = memory_manager.add_item_from_image(
                image_bytes=entry['image_bytes'], type_name=type_name, concept=concept,
                tags=list({*(cand.get('tags') or []), concept, query, type_name}), source=cand.get('provider') or 'unknown',
                source_url=cand.get('source_url'), author=cand.get('author'), license_name=cand.get('license'),
                title=cand.get('title'), query=query, quality_score=entry['quality_score'], relevance_score=entry['relevance_score'],
                approved=state == 'approved', status=state, metadata=metadata,
                similarity_threshold=cfg['similarity_threshold'],
            )
            if result.get('saved'):
                if shortlisted: saved_candidates.append(result['item'])
                else: saved_rejected.append(result['item'])

        rejection_reasons: dict[str, int] = {}
        for entry in rejected:
            reason = str(entry.get('reason') or 'desconhecido')
            key = reason[:160]
            rejection_reasons[key] = rejection_reasons.get(key, 0) + 1

        diagnostics = {
            'provider_errors': list(search['errors']),
            'provider_trace': list(search.get('provider_trace') or []),
            'candidates_found': len(search['candidates']),
            'kept_after_filter': len(kept),
            'saved_count': len(saved_candidates),
            'saved_rejected_count': len(saved_rejected),
            'top_rejection_reasons': sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)[:8],
            'candidates_processed': candidates_processed,
            'budget_exhausted': budget_exhausted,
            'processing_ms': int((time.monotonic() - collect_started) * 1000),
        }

        history = {
            'query': query, 'providers': search['providers'], 'results_found': len(search['candidates']),
            'downloaded': len(kept) + len(saved_rejected), 'rejected': len(rejected),
            'candidates_saved': sum(1 for x in saved_candidates if x.get('status') == 'candidates'),
            'approved': sum(1 for x in saved_candidates if x.get('status') == 'approved'),
            'filters': cfg, 'search_metadata': search_metadata or {}, 'date': time.time(),
        }
        memory_manager.record_search_history(type_name=type_name, concept=concept, entry=history)
        return {
            'query': query, 'concept': concept, 'type': type_name, 'providers': search['providers'], 'errors': search['errors'], 'provider_trace': search.get('provider_trace') or [],
            'filters': cfg, 'candidates_found': len(search['candidates']), 'kept_after_filter': len(kept),
            'rejected_count': len(rejected), 'rejected': rejected[:100], 'saved_count': len(saved_candidates),
            'saved_items': saved_candidates, 'saved_rejected_count': len(saved_rejected), 'search_history_entry': history, 'diagnostics': diagnostics,
            'top_candidates': [{
                'provider': x['candidate'].get('provider'), 'title': x['candidate'].get('title'),
                'source_url': x['candidate'].get('source_url'), 'image_url': x['candidate'].get('image_url'),
                'quality_score': x['quality_score'], 'relevance_score': x['relevance_score'], 'composition_score': x.get('composition_score'), 'combined_score': x['combined_score'],
                'width': x['inspection']['width'], 'height': x['inspection']['height'],
                'isolation_score': x['inspection'].get('isolation_score'), 'cutout_score': x['inspection'].get('cutout_score'), 'cutout_compatible': x['inspection'].get('cutout_compatible'),
                'transparent_pixel_ratio': x['inspection'].get('transparent_pixel_ratio'), 'alpha_foreground_ratio': x['inspection'].get('alpha_foreground_ratio'),
                'alpha_border_foreground_ratio': x['inspection'].get('alpha_border_foreground_ratio'), 'border_uniformity': x['inspection'].get('border_uniformity'),
            } for x in kept[:20]],
        }


collector_service = CollectorService()
