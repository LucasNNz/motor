from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PIL import Image

from .collector_service import collector_service
from .composer_engine import composer_engine
from .guide_parser import TYPE_BY_SEARCH_SECTION, guide_parser, ParsedGuide
from .memory_manager import memory_manager
from .operation_manager import operation_manager
from .refiner import build_refiner
from .reference_conditioning import reference_conditioning_builder, VisualReferenceBundle
from .reprocessor import regional_reprocessor


class GuidedExecutionService:
    def validate_contract(self, guide: ParsedGuide) -> dict[str, Any]:
        """Validate execution-critical guide fields without inventing intent.

        The external AI owns planning. The Engine only verifies that a guided MVP
        contract is explicit enough to execute deterministically. For values that
        intentionally do not constrain the image, the guide can use `free`.
        """
        root = dict(guide.first('CORVO_IMAGE_GUIDE') or {})
        subject = dict(guide.first('SUBJECT') or {})
        comp = dict(guide.first('COMPOSITION') or {})
        output = dict(guide.first('OUTPUT') or {})
        render = dict(guide.first('RENDER') or {})
        object_searches = [block for section, block in guide.search_blocks() if section == 'SEARCH_OBJECT']
        task = str(root.get('task') or '').strip().lower()
        mode = str(root.get('mode') or '').strip().lower()
        issues: list[str] = []
        warnings: list[str] = []

        if mode == 'guided' and not guide.search_blocks():
            issues.append('nenhum bloco SEARCH_* foi informado')

        if task == 'single_object_quiz':
            if str(subject.get('type') or '').strip().lower() not in {'object','objeto'}:
                issues.append('[SUBJECT] type=object')
            if not subject.get('name'):
                issues.append('[SUBJECT] name=...')
            if not object_searches or not object_searches[0].get('query'):
                issues.append('[SEARCH_OBJECT] query=...')

            orientation = (
                subject.get('orientation')
                or (object_searches[0].get('orientation') if object_searches else None)
                or comp.get('subject_orientation')
            )
            desired_view = (
                subject.get('desired_view') or subject.get('view')
                or (object_searches[0].get('desired_view') if object_searches else None)
                or (object_searches[0].get('view') if object_searches else None)
            )
            if not orientation:
                issues.append('orientation=vertical|horizontal|free em [SUBJECT] ou [SEARCH_OBJECT]')
            if not desired_view:
                issues.append('desired_view=front|side|3/4|free em [SUBJECT] ou [SEARCH_OBJECT]')

            for field in ('subject_x','subject_y','subject_scale'):
                if field not in comp:
                    issues.append(f'[COMPOSITION] {field}=...')
            if not (output.get('width') and output.get('height')) and not output.get('aspect_ratio'):
                issues.append('[OUTPUT] width/height ou aspect_ratio')
            if not render:
                issues.append('[RENDER] com diretivas de preservação/refino')

            # View is semantic and cannot be reliably inferred by the current non-LLM Engine.
            # The query should therefore mention the requested view when it is constrained.
            view_norm = str(desired_view or '').strip().lower()
            if view_norm not in {'', 'free', 'livre', 'none'} and object_searches:
                query_text = ' '.join(str(object_searches[0].get(k) or '') for k in ('query','fallback_queries','query_fallbacks')).lower()
                view_terms = {
                    'front': ('front','frontal','top view'), 'frontal': ('front','frontal','top view'),
                    'side': ('side','lateral'), 'lateral': ('side','lateral'),
                    '3/4': ('3/4','three quarter','three-quarter'),
                }.get(view_norm, (view_norm,))
                if not any(term in query_text for term in view_terms):
                    warnings.append(f'desired_view={desired_view} não aparece nas queries de SEARCH_OBJECT; o Engine não consegue validar perspectiva visual sozinho')

        return {
            'valid': not issues, 'issues': issues, 'warnings': warnings,
            'task': task or None, 'mode': mode or None,
        }

    def _filter_config(self, guide: ParsedGuide) -> dict[str, Any]:
        # FILTER remains the explicit source of technical thresholds. A few visual
        # constraints are deterministically projected from the guide so the engine
        # actually executes directives such as SUBJECT isolated=true instead of merely
        # storing them as prose. No semantic inference/LLM is involved here.
        cfg = dict(guide.first('FILTER') or {})
        subject = dict(guide.first('SUBJECT') or {})
        negative = dict(guide.first('NEGATIVE') or {})
        background = dict(guide.first('BACKGROUND') or {})
        if subject.get('isolated') is True:
            cfg.setdefault('require_isolated', True)
            cfg.setdefault('min_isolation_score', 0.68)
        if negative.get('busy_background') is True:
            cfg.setdefault('reject_busy_background', True)
        brightness = str(background.get('brightness') or '').strip().lower()
        if brightness in {'light', 'claro', 'bright'}:
            cfg.setdefault('prefer_light_background', True)
        return cfg

    def _search_spec(self, section: str, block: dict[str, Any]) -> dict[str, Any]:
        type_name = TYPE_BY_SEARCH_SECTION.get(section, 'other')
        query = str(block.get('query') or block.get('reference_target') or block.get('environment') or block.get('pose') or block.get('object') or type_name)
        concept = str(block.get('reference_target') or block.get('environment') or block.get('pose') or block.get('object') or query)
        return {
            'section': section, 'type': type_name, 'query': query, 'concept': concept,
            'collect_limit': int(block.get('collect_limit') or 40),
            'keep_limit': int(block.get('keep_limit') or 10),
            'block': block,
        }

    @staticmethod
    def _providers_for_spec(block: dict[str, Any], defaults: list[str]) -> list[str]:
        value = block.get('providers', block.get('provider'))
        if not value:
            return list(defaults)
        if isinstance(value, str):
            values = [x.strip() for x in value.split(',') if x.strip()]
        elif isinstance(value, (list, tuple)):
            values = [str(x).strip() for x in value if str(x).strip()]
        else:
            values = [str(value).strip()]
        aliases = {
            'wikimedia': 'wikimedia_commons', 'commons': 'wikimedia_commons',
            'open_verse': 'openverse', 'open-verse': 'openverse',
        }
        return [aliases.get(x.lower(), x.lower()) for x in values] or list(defaults)

    @staticmethod
    def _queries_for_spec(spec: dict[str, Any]) -> list[str]:
        block = spec.get('block') or {}
        primary = str(spec.get('query') or '').strip()
        values: list[str] = [primary] if primary else []
        raw = block.get('fallback_queries', block.get('query_fallbacks'))
        if isinstance(raw, str):
            values.extend(x.strip() for x in raw.split('|') if x.strip())
        elif isinstance(raw, (list, tuple)):
            values.extend(str(x).strip() for x in raw if str(x).strip())
        # Also accept query_fallback_1=..., query_fallback_2=... for TXT generators
        # that prefer one key per line.
        numbered = []
        for key, value in block.items():
            key_s = str(key).lower()
            if key_s.startswith('query_fallback_') and value:
                try:
                    idx = int(key_s.rsplit('_', 1)[1])
                except Exception:
                    idx = 999
                numbered.append((idx, str(value).strip()))
        values.extend(v for _, v in sorted(numbered) if v)
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.casefold()
            if value and key not in seen:
                seen.add(key); out.append(value)
        return out or [primary]

    @staticmethod
    def _effective_limits(spec: dict[str, Any], *, fast_mvp: bool) -> tuple[int, int]:
        collect_limit = max(1, int(spec.get('collect_limit') or 40))
        keep_limit = max(1, int(spec.get('keep_limit') or 10))
        if fast_mvp:
            # Production MVP prioritizes latency. The requested values remain in logs.
            collect_limit = min(collect_limit, 6)
            keep_limit = min(keep_limit, 2)
        return collect_limit, min(keep_limit, collect_limit)

    @staticmethod
    def _search_required(block: dict[str, Any]) -> bool:
        if block.get('required') is False:
            return False
        fallback = str(block.get('fallback') or '').strip().lower()
        if fallback in {'demo', 'allow_demo', 'optional', 'skip'}:
            return False
        return True

    @staticmethod
    def _round8(value: float) -> int:
        return max(64, int(round(float(value) / 8.0) * 8))

    def _resolve_output_size(self, guide: ParsedGuide, width: int, height: int) -> tuple[int, int, dict[str, Any]]:
        out = dict(guide.first('OUTPUT') or {})
        requested = {'ui_width': int(width), 'ui_height': int(height), **out}
        explicit_w = out.get('width')
        explicit_h = out.get('height')
        if explicit_w and explicit_h:
            return self._round8(float(explicit_w)), self._round8(float(explicit_h)), requested
        size = str(out.get('size') or '').lower().replace(' ', '')
        if 'x' in size:
            try:
                w, h = size.split('x', 1)
                return self._round8(float(w)), self._round8(float(h)), requested
            except Exception:
                pass
        ratio = str(out.get('aspect_ratio') or '').strip()
        if ':' in ratio:
            try:
                rw, rh = [float(x.strip()) for x in ratio.split(':', 1)]
                if rw > 0 and rh > 0:
                    short = max(256, min(int(width), int(height)))
                    if rw >= rh:
                        resolved_h = short
                        resolved_w = short * rw / rh
                    else:
                        resolved_w = short
                        resolved_h = short * rh / rw
                    return self._round8(resolved_w), self._round8(resolved_h), requested
            except Exception:
                pass
        return int(width), int(height), requested

    def _validate_required_searches(self, guide: ParsedGuide, *, allow_candidates: bool, search_log: list[dict[str, Any]] | None = None) -> None:
        missing: list[str] = []
        search_log = list(search_log or [])
        for spec in self._all_search_specs(guide):
            if not self._search_required(spec['block']):
                continue
            found = memory_manager.search_best(
                spec['concept'], spec['type'], limit=1, approved_only=not allow_candidates
            )
            if found:
                continue
            detail = f"{spec['section']} query={spec['query']!r} concept={spec['concept']!r}"
            entry = next((x for x in search_log if (x.get('spec') or {}).get('section') == spec['section'] and (x.get('spec') or {}).get('query') == spec['query']), None)
            result = (entry or {}).get('result') or {}
            diag = result.get('diagnostics') or {}
            if diag:
                detail += (
                    f" [encontrados={diag.get('candidates_found', 0)}, passaram_filtro={diag.get('kept_after_filter', 0)}, "
                    f"salvos={diag.get('saved_count', 0)}"
                )
                provider_errors = diag.get('provider_errors') or []
                if provider_errors:
                    detail += f", erros_provider={' | '.join(str(x) for x in provider_errors[:3])}"
                reasons = diag.get('top_rejection_reasons') or []
                if reasons:
                    detail += ', rejeicoes=' + ' | '.join(f"{reason} ({count})" for reason, count in reasons[:4])
                if diag.get('budget_exhausted'):
                    detail += ', budget_coleta=esgotado'
                if diag.get('candidates_processed') is not None:
                    detail += f", processados={diag.get('candidates_processed')}"
                if diag.get('processing_ms') is not None:
                    detail += f", tempo_coleta_ms={diag.get('processing_ms')}"
                attempts = diag.get('query_attempts') or []
                if attempts:
                    compact = []
                    for attempt in attempts[:4]:
                        compact.append(f"{attempt.get('query')!r}:{attempt.get('found', 0)}→{attempt.get('saved', 0)}")
                    detail += ', tentativas=' + ' | '.join(compact)
                traces = diag.get('provider_trace') or []
                if traces:
                    compact = []
                    for trace in traces[:4]:
                        compact.append(f"{trace.get('provider')}:{trace.get('status')}:{trace.get('found', 0)}:{trace.get('elapsed_ms', 0)}ms")
                    detail += ', providers=' + ' | '.join(compact)
                detail += ']'
            missing.append(detail)
        if missing:
            raise RuntimeError(
                'Busca obrigatória sem referência utilizável. O Engine não usará asset demo silenciosamente: ' + '; '.join(missing)
            )

    def _all_search_specs(self, guide: ParsedGuide) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        explicit_types: set[str] = set()
        for section, block in guide.search_blocks():
            spec = self._search_spec(section, block)
            specs.append(spec); explicit_types.add(spec['type'])

        # Compatibility with the compact [SEARCH] form from the architecture notes.
        generic = guide.first('SEARCH') or {}
        generic_map = {
            'character_reference': 'character', 'character': 'character',
            'lighting': 'lighting', 'camera_reference': 'camera', 'camera': 'camera',
            'background': 'background', 'environment': 'background', 'village': 'background',
            'object': 'object', 'chair': 'object',
        }
        for key, value in generic.items():
            type_name = generic_map.get(key)
            if type_name is None and str(key).startswith('pose'):
                type_name = 'pose'
            if not type_name or type_name in explicit_types:
                continue
            section = f'SEARCH_{type_name.upper()}'
            block = {'query': f'{key} {value}', key: value}
            spec = self._search_spec(section, block); spec['type'] = type_name
            specs.append(spec); explicit_types.add(type_name)

        # If a component exists in SCENE but has no explicit SEARCH block, create a minimal directed search.
        scene = guide.first('SCENE') or {}
        scene_specs = [
            ('character', scene.get('visual_reference') or scene.get('character'), 'reference_target'),
            ('pose', scene.get('action'), 'pose'),
            ('face', scene.get('emotion'), 'expression'),
            ('object', scene.get('object'), 'object'),
            ('background', scene.get('environment'), 'environment'),
            ('camera', scene.get('camera'), 'camera'),
        ]
        for type_name, value, field in scene_specs:
            if not value or type_name in explicit_types:
                continue
            section = f'SEARCH_{type_name.upper()}'
            block = {'query': str(value), field: value, 'collect_limit': 40, 'keep_limit': 8}
            spec = self._search_spec(section, block); spec['type'] = type_name
            specs.append(spec); explicit_types.add(type_name)
        return specs

    def collect_from_guide(self, guide_text: str, *, providers: list[str], auto_approve: bool = False, fast_mvp: bool = False) -> dict[str, Any]:
        guide = guide_parser.parse(guide_text)
        filters = self._filter_config(guide)
        results = []
        global_started = time.monotonic()
        global_budget = 42.0 if fast_mvp else None
        for spec in self._all_search_specs(guide):
            section = spec['section']; block = spec['block']

            # In the production MVP, an optional fallback search of the same component
            # is skipped once a usable candidate already exists. This avoids spending
            # serverless time on a second provider that the guide marked optional.
            if fast_mvp and not self._search_required(block):
                existing = memory_manager.search_best(spec['concept'], spec['type'], limit=1, approved_only=False)
                if existing:
                    results.append({
                        'spec': spec, 'providers': self._providers_for_spec(block, providers),
                        'skipped': True, 'skip_reason': 'optional_fallback_already_satisfied',
                        'result': {
                            'query': spec['query'], 'concept': spec['concept'], 'type': spec['type'],
                            'saved_count': 0, 'diagnostics': {
                                'candidates_found': 0, 'kept_after_filter': 0, 'saved_count': 0,
                                'provider_errors': [], 'skipped': True,
                                'skip_reason': 'optional_fallback_already_satisfied',
                            },
                        },
                    })
                    continue

            remaining = None if global_budget is None else max(0.0, global_budget - (time.monotonic() - global_started))
            if remaining is not None and remaining < 2.0:
                results.append({
                    'spec': spec, 'providers': self._providers_for_spec(block, providers),
                    'skipped': True, 'skip_reason': 'global_fast_mvp_time_budget',
                    'result': {
                        'query': spec['query'], 'concept': spec['concept'], 'type': spec['type'],
                        'saved_count': 0, 'diagnostics': {
                            'candidates_found': 0, 'kept_after_filter': 0, 'saved_count': 0,
                            'provider_errors': ['orçamento global de coleta do MVP esgotado'],
                            'budget_exhausted': True,
                        },
                    },
                })
                continue

            spec_providers = self._providers_for_spec(block, providers)
            collect_limit, keep_limit = self._effective_limits(spec, fast_mvp=fast_mvp)
            per_spec_budget = min(10.0, remaining) if remaining is not None else None
            query_sequence = self._queries_for_spec(spec)
            query_attempts: list[dict[str, Any]] = []
            aggregate_trace: list[dict[str, Any]] = []
            aggregate_errors: list[str] = []
            aggregate_found = 0
            aggregate_processed = 0
            aggregate_kept = 0
            aggregate_saved = 0
            aggregate_rejected_reasons: dict[str, int] = {}
            aggregate_started = time.monotonic()
            result: dict[str, Any] | None = None
            for query_index, query_value in enumerate(query_sequence):
                remaining_spec = None if per_spec_budget is None else max(0.0, per_spec_budget - (time.monotonic() - aggregate_started))
                if remaining_spec is not None and remaining_spec < 1.0:
                    break
                attempt = collector_service.collect(
                    query=query_value, type_name=spec['type'], concept=spec['concept'], providers=spec_providers,
                    per_provider=min(12, max(2, collect_limit // max(1, len(spec_providers)))),
                    save_limit=keep_limit, keep_limit=keep_limit, collect_limit=collect_limit,
                    auto_approve=auto_approve, filters=filters, provider_options=block,
                    processing_budget_seconds=remaining_spec,
                    max_download_attempts=2 if fast_mvp else None,
                    stop_when_kept=fast_mvp,
                    search_metadata={
                        'section': section, **block, 'query_attempt_index': query_index,
                        'query_original': spec['query'], 'query_effective': query_value,
                        'providers_effective': spec_providers,
                        'collect_limit_requested': spec['collect_limit'], 'collect_limit_effective': collect_limit,
                        'keep_limit_requested': spec['keep_limit'], 'keep_limit_effective': keep_limit,
                        'fast_mvp': fast_mvp, 'processing_budget_seconds': remaining_spec,
                    },
                )
                result = attempt
                diag = attempt.get('diagnostics') or {}
                query_attempts.append({
                    'query': query_value,
                    'found': diag.get('candidates_found', 0),
                    'processed': diag.get('candidates_processed', 0),
                    'kept': diag.get('kept_after_filter', 0),
                    'saved': diag.get('saved_count', 0),
                    'elapsed_ms': diag.get('processing_ms', 0),
                    'provider_errors': diag.get('provider_errors') or [],
                })
                aggregate_trace.extend(diag.get('provider_trace') or [])
                aggregate_errors.extend(diag.get('provider_errors') or [])
                aggregate_found += int(diag.get('candidates_found') or 0)
                aggregate_processed += int(diag.get('candidates_processed') or 0)
                aggregate_kept += int(diag.get('kept_after_filter') or 0)
                aggregate_saved += int(diag.get('saved_count') or 0)
                for reason, count in (diag.get('top_rejection_reasons') or []):
                    aggregate_rejected_reasons[str(reason)] = aggregate_rejected_reasons.get(str(reason), 0) + int(count)
                # The guide supplied the fallback order. Stop at the first query
                # that produces a usable reference for this component.
                if int(diag.get('saved_count') or 0) > 0:
                    break
            if result is None:
                result = {
                    'query': spec['query'], 'concept': spec['concept'], 'type': spec['type'], 'saved_count': 0,
                    'diagnostics': {},
                }
            result['query_original'] = spec['query']
            result['query_attempts'] = query_attempts
            result['diagnostics'] = {
                **(result.get('diagnostics') or {}),
                'candidates_found': aggregate_found,
                'candidates_processed': aggregate_processed,
                'kept_after_filter': aggregate_kept,
                'saved_count': aggregate_saved,
                'provider_errors': aggregate_errors,
                'provider_trace': aggregate_trace,
                'query_attempts': query_attempts,
                'top_rejection_reasons': sorted(aggregate_rejected_reasons.items(), key=lambda x: x[1], reverse=True)[:8],
                'processing_ms': int((time.monotonic() - aggregate_started) * 1000),
            }
            results.append({
                'spec': spec, 'providers': spec_providers,
                'effective_collect_limit': collect_limit, 'effective_keep_limit': keep_limit,
                'query_sequence': query_sequence, 'result': result,
            })
        composer_engine.reload_memory()
        return {
            'guide': guide.as_dict(), 'filters': filters, 'results': results,
            'memory': memory_manager.status(), 'fast_mvp': fast_mvp,
            'collect_total_ms': int((time.monotonic() - global_started) * 1000),
            'collect_budget_seconds': global_budget,
        }

    def _should_collect(self, guide: ParsedGuide, *, allow_candidates: bool = False) -> bool:
        for spec in self._all_search_specs(guide):
            if not memory_manager.search_best(spec['concept'], spec['type'], limit=1, approved_only=not allow_candidates):
                return True
        return False

    def _reference_overrides_from_search_log(self, guide: ParsedGuide, search_log: list[dict[str, Any]], *, allow_candidates: bool) -> dict[str, str]:
        """Pin references selected by this operation before the Composer runs.

        The library remains reusable, but a freshly collected reference must not lose
        to an older candidate left in a warm serverless /tmp. The first search block
        for each component has priority; later blocks are fallbacks.
        """
        overrides: dict[str, str] = {}
        for entry in search_log or []:
            spec = entry.get('spec') or {}
            type_name = str(spec.get('type') or '').strip()
            if not type_name or type_name in overrides:
                continue
            result = entry.get('result') or {}
            saved = list(result.get('saved_items') or [])
            chosen = next((x for x in saved if x.get('id') and x.get('status') != 'rejected' and not x.get('blocked')), None)
            if chosen:
                overrides[type_name] = chosen['id']
                entry['selected_for_operation'] = chosen['id']
                continue
            # If this exact source/hash was already in the library, collection records
            # it as a duplicate. Reuse that exact item instead of running a new global
            # ranking that could select an unrelated older candidate.
            duplicate = next((
                x for x in (result.get('rejected') or [])
                if x.get('library_id') and 'já existe na biblioteca' in str(x.get('reason') or '')
            ), None)
            if duplicate and memory_manager.by_id.get(duplicate['library_id']):
                overrides[type_name] = duplicate['library_id']
                entry['selected_for_operation'] = duplicate['library_id']
                entry['selected_reason'] = 'duplicate_reused'
                continue
            matches = list(entry.get('library_matches') or [])
            chosen_match = next((x for x in matches if x.get('id') and x.get('status') != 'rejected'), None)
            if chosen_match:
                overrides[type_name] = chosen_match['id']
                entry['selected_for_operation'] = chosen_match['id']

        # Duplicate downloads or a skipped optional block can legitimately produce no
        # saved_items even though the library contains a usable reference. Resolve only
        # missing component types here; never replace a current-operation pin.
        for spec in self._all_search_specs(guide):
            type_name = spec['type']
            if type_name in overrides:
                continue
            found = memory_manager.search_best(spec['concept'], type_name, limit=1, approved_only=not allow_candidates)
            if found:
                overrides[type_name] = found[0]['id']
        return overrides

    def _selected_references(self, guide: ParsedGuide, composition: dict[str, Any], *, allow_candidates: bool = False) -> list[dict[str, Any]]:
        refs: dict[str, dict[str, Any]] = {}
        plan = (composition or {}).get('plan') or {}
        for label in ['background', 'pose', 'face', 'outfit', 'object']:
            item = plan.get(label) or {}
            item_id = item.get('id')
            if item_id:
                refs[f'composer_{label}'] = {'label': f'composer_{label}', 'id': item_id, 'source': item.get('source'), 'file': item.get('file')}
        plan_type_map = {
            'background': plan.get('background') or {},
            'pose': plan.get('pose') or {},
            'face': plan.get('face') or {},
            'expression': plan.get('face') or {},
            'object': plan.get('object') or {},
            'clothes': plan.get('outfit') or {},
            'outfit': plan.get('outfit') or {},
        }
        for spec in self._all_search_specs(guide):
            type_name = spec['type']
            selected = plan_type_map.get(type_name) or {}
            selected_id = selected.get('id')
            if selected_id and memory_manager.by_id.get(selected_id):
                item = memory_manager.by_id[selected_id]
            else:
                found = memory_manager.search_best(spec['concept'], type_name, limit=1, approved_only=not allow_candidates)
                if not found:
                    continue
                item = found[0]
            refs[f"guide_{type_name}"] = {
                'label': f"guide_{type_name}", 'id': item['id'], 'source': item.get('source'),
                'file': item.get('local_path'), 'concept': item.get('concept'), 'query': spec['query'],
                'preferred': item.get('preferred'), 'success_rate': item.get('success_rate', 0), 'status': item.get('status'),
            }
        return list(refs.values())

    def _guided_refiner_prompt(self, prompt: str, guide: ParsedGuide) -> str:
        scene = guide.first('SCENE')
        render = guide.first('RENDER')
        parts = [prompt.strip()] if prompt.strip() else []
        if scene:
            parts.append('SCENE: ' + ', '.join(f'{k}={v}' for k, v in scene.items()))
        if render:
            preserve = [k for k, v in render.items() if str(k).startswith('preserve_') and v]
            active = [k for k, v in render.items() if v and k not in preserve]
            if preserve: parts.append('PRESERVE: ' + ', '.join(preserve))
            if active: parts.append('REFINE: ' + ', '.join(active))
        return '. '.join(parts) or 'guided image refinement, preserve composition and identity'

    def execute(self, *, prompt: str, guide_text: str, width: int, height: int, refiner_name: str = 'none',
                steps: int = 3, strength: float = 0.24, collect_missing: bool = False,
                auto_approve_collected: bool = False, allow_candidates: bool = False,
                providers: list[str] | None = None, fast_mvp: bool = False) -> dict[str, Any]:
        guide = guide_parser.parse(guide_text)
        contract = self.validate_contract(guide)
        if not contract['valid']:
            raise ValueError('Guia incompleto para execução determinística: ' + '; '.join(contract['issues']))
        width, height, output_request = self._resolve_output_size(guide, width, height)
        providers = list(providers or ['openverse', 'wikimedia_commons'])
        operation_id = operation_manager.create(prompt=prompt, guide_text=guide_text)
        started = time.perf_counter()
        search_log: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        try:
            if collect_missing and (fast_mvp or self._should_collect(guide, allow_candidates=allow_candidates)):
                collect_started = time.perf_counter()
                collected = self.collect_from_guide(guide_text, providers=providers, auto_approve=auto_approve_collected, fast_mvp=fast_mvp)
                search_log = collected['results']
                collect_ms = int((time.perf_counter() - collect_started) * 1000)
            else:
                collect_ms = 0
                for spec in self._all_search_specs(guide):
                    found = memory_manager.search_best(spec['concept'], spec['type'], limit=10, approved_only=not allow_candidates)
                    search_log.append({'spec': spec, 'library_matches': [{'id': x['id'], 'status': x.get('status')} for x in found]})

            # Explicit SEARCH_* blocks are instructions, not suggestions. Unless the
            # TXT marks a block optional/fallback, do not hide a failed search by
            # silently substituting an unrelated demo asset.
            self._validate_required_searches(guide, allow_candidates=allow_candidates, search_log=search_log)
            reference_overrides = self._reference_overrides_from_search_log(
                guide, search_log, allow_candidates=allow_candidates
            )

            compose_started = time.perf_counter()
            base = composer_engine.generate_guided(
                guide, width, height, allow_candidates=allow_candidates,
                reference_overrides=reference_overrides,
            )
            composer_ms = int((time.perf_counter() - compose_started) * 1000)
            composition = composer_engine.last_info
            composition['output'] = {
                'width': width, 'height': height, 'aspect_ratio': f'{width}:{height}',
                'guide_request': output_request,
            }
            operation_manager.save_image(operation_id, 'etapas/composicao_base.png', base)
            operation_manager.save_image(operation_id, 'etapas/antes_refinamento.png', base)

            references = self._selected_references(guide, composition, allow_candidates=allow_candidates)
            copied = []
            for ref in references:
                item = memory_manager.by_id.get(ref.get('id'))
                if item:
                    path = memory_manager.path_for(item)
                else:
                    # Demo bank asset: locate through Composer's visual bank.
                    asset = next((a for a in composer_engine.bank.assets if a.get('id') == ref.get('id')), None)
                    path = composer_engine.bank.asset_path(asset) if asset else Path('/missing')
                rel = operation_manager.copy_reference(operation_id, path, ref.get('label') or ref.get('id') or 'ref')
                ref['operation_copy'] = rel
                copied.append(ref)

            refine_ms = 0
            refiner_log: dict[str, Any] = {'backend': 'none', 'generative': False}
            conditioning_log: dict[str, Any] = {'requested': False, 'bundle': {}}
            final = base
            if refiner_name and refiner_name != 'none':
                refiner = build_refiner(refiner_name)
                ref_prompt = self._guided_refiner_prompt(prompt, guide)
                bundle = reference_conditioning_builder.build(
                    copied,
                    output_size=(width, height),
                    guide_render=guide.first('RENDER') or {},
                )
                conditioning_log = {'requested': bundle.requested(), 'bundle': bundle.metadata}
                if bundle.control_image is not None:
                    operation_manager.save_image(operation_id, 'etapas/pose_control.png', bundle.control_image)
                result = refiner.refine(base, ref_prompt, strength=strength, steps=steps, references=bundle)
                final = result.image
                refine_ms = result.duration_ms
                refiner_log = {'backend': result.backend, **result.metadata, 'guided_prompt': ref_prompt}
                conditioning_log['applied'] = result.metadata.get('conditioning_applied', [])
                conditioning_log['fallback'] = result.metadata.get('conditioning_fallback')
            operation_manager.save_image(operation_id, 'etapas/depois_refinamento.png', final)
            operation_manager.save_image(operation_id, 'resultado_final.png', final)

            total_ms = int((time.perf_counter() - started) * 1000)
            operation_manager.write_json(operation_id, 'logs/buscas.json', search_log)
            operation_manager.write_json(operation_id, 'logs/referencias.json', {'used': copied})
            library_ids = [x.get('id') for x in copied if x.get('id') in memory_manager.by_id]
            memory_manager.register_operation_use(library_ids, operation_id)
            operation_manager.write_json(operation_id, 'logs/composicao.json', composition)
            operation_manager.write_json(operation_id, 'logs/execucao.json', {
                'mode': 'guided_fast_mvp' if fast_mvp else 'guided',
                'allow_candidates': allow_candidates, 'auto_approve_collected': auto_approve_collected,
                'providers_default': providers, 'collect_missing': collect_missing,
                'reference_overrides': reference_overrides,
                'output_resolved': {'width': width, 'height': height, 'guide_request': output_request},
            })
            operation_manager.write_json(operation_id, 'logs/refinador.json', refiner_log)
            operation_manager.write_json(operation_id, 'logs/condicionamento.json', conditioning_log)
            operation_manager.write_json(operation_id, 'logs/tempos.json', {
                'collect_ms': collect_ms, 'composer_ms': composer_ms, 'refiner_ms': refine_ms, 'total_ms': total_ms,
            })
            operation_manager.write_json(operation_id, 'logs/erros.json', errors)
            operation_manager.write_json(operation_id, 'logs/avaliacao.json', {'approved': None, 'scores': {}, 'notes': ''})
            operation_manager.finish(operation_id, status='done', diagnostic='Execução guiada concluída. Avaliação manual pendente.')
            return {
                'operation_id': operation_id, 'image': final, 'composition': composition, 'references': copied,
                'timings': {'collect_ms': collect_ms, 'composer_ms': composer_ms, 'refiner_ms': refine_ms, 'total_ms': total_ms},
                'refiner': refiner_log, 'guide': guide.as_dict(), 'searches': search_log, 'guide_contract': contract,
                'execution': {
                    'allow_candidates': allow_candidates, 'fast_mvp': fast_mvp, 'providers': providers,
                    'reference_overrides': reference_overrides,
                    'output': {'width': width, 'height': height, 'guide_request': output_request},
                },
            }
        except Exception as exc:
            errors.append({'stage': 'guided_execution', 'error': str(exc), 'at': time.time()})
            if search_log:
                operation_manager.write_json(operation_id, 'logs/buscas.json', search_log)
            operation_manager.write_json(operation_id, 'logs/erros.json', errors)
            operation_manager.finish(operation_id, status='error', diagnostic=str(exc))
            raise


    def reprocess(self, *, parent_operation_id: str, correction_guide_text: str, refiner_name: str = 'light_cpu',
                  steps: int = 3, strength: float = 0.24) -> dict[str, Any]:
        parent_root = operation_manager.root_for(parent_operation_id)
        parent_result = parent_root / 'resultado_final.png'
        if not parent_result.exists():
            raise KeyError(parent_operation_id)

        correction = guide_parser.parse(correction_guide_text)
        reprocess = correction.first('REPROCESS') or {}
        fixes = correction.all('FIX')
        if not fixes:
            raise ValueError('O guia de correção precisa possuir pelo menos um bloco [FIX].')
        if reprocess.get('reuse_previous_scene') is False:
            raise ValueError('O reprocessamento regional exige reuse_previous_scene=true. Para reconstruir a cena, execute um novo guia.')

        prompt = operation_manager.read_text(parent_operation_id, 'pedido_original.txt', '')
        base_guide = operation_manager.read_text(parent_operation_id, 'guia_auxiliar.txt', '')
        parent_composition = operation_manager.read_json(parent_operation_id, 'logs/composicao.json', {}) or {}
        parent_refs = operation_manager.read_json(parent_operation_id, 'logs/referencias.json', {'used': []}) or {'used': []}

        child_id = operation_manager.create(
            prompt=prompt,
            guide_text=correction_guide_text,
            parent_operation_id=parent_operation_id,
            kind='regional_reprocess',
        )
        child_root = operation_manager.root_for(child_id)
        (child_root / 'guia_base.txt').write_text(base_guide, encoding='utf-8')
        (child_root / 'guia_correcao.txt').write_text(correction_guide_text, encoding='utf-8')
        operation_manager.copy_parent_references(parent_operation_id, child_id)

        started = time.perf_counter()
        errors: list[dict[str, Any]] = []
        fix_logs: list[dict[str, Any]] = []
        try:
            current = Image.open(parent_result).convert('RGB')
            operation_manager.save_image(child_id, 'etapas/original_pai.png', current)
            operation_manager.save_image(child_id, 'etapas/antes_refinamento.png', current)

            # Regional repair should preserve the successful composition. In V0.9
            # we reuse only the identity signal from the parent operation; a full
            # pose ControlNet on a cropped hand/face would be spatially misleading.
            parent_bundle = reference_conditioning_builder.build(
                inherited_refs := list((parent_refs or {}).get('used') or []),
                output_size=current.size,
                guide_render=reprocess,
            )
            repair_bundle = VisualReferenceBundle(
                identity_image=parent_bundle.identity_image,
                metadata={
                    **parent_bundle.metadata,
                    'scope': 'regional_identity_only',
                    'pose_control_disabled_for_crop': True,
                },
            )

            for index, fix in enumerate(fixes, 1):
                operation_manager.save_image(child_id, f'etapas/fix_{index:02d}_antes.png', current)
                current, log, mask = regional_reprocessor.apply_fix(
                    current,
                    fix=fix,
                    reprocess=reprocess,
                    composition=parent_composition,
                    refiner_name=refiner_name,
                    steps=steps,
                    strength=strength,
                    references=repair_bundle,
                )
                operation_manager.save_image(child_id, f'etapas/fix_{index:02d}_mascara.png', mask)
                operation_manager.save_image(child_id, f'etapas/fix_{index:02d}_depois.png', current)
                log['index'] = index
                fix_logs.append(log)

            total_ms = int((time.perf_counter() - started) * 1000)
            operation_manager.save_image(child_id, 'etapas/depois_refinamento.png', current)
            operation_manager.save_image(child_id, 'resultado_final.png', current)

            child_refs = {
                'used': inherited_refs,
                'inherited_from_operation': parent_operation_id,
                'reference_files_copied': True,
            }
            operation_manager.write_json(child_id, 'logs/buscas.json', {
                'inherited_from_operation': parent_operation_id,
                'new_searches': [],
                'reason': 'Reprocessamento regional reutiliza a cena e as referências anteriores.',
            })
            operation_manager.write_json(child_id, 'logs/referencias.json', child_refs)
            operation_manager.write_json(child_id, 'logs/composicao.json', {
                'inherited_from_operation': parent_operation_id,
                'base_composition': parent_composition,
                'reprocess': reprocess,
            })
            operation_manager.write_json(child_id, 'logs/reprocessamento.json', {
                'parent_operation_id': parent_operation_id,
                'reuse_previous_scene': reprocess.get('reuse_previous_scene', True),
                'preserve_flags': {k: v for k, v in reprocess.items() if k.startswith('preserve_')},
                'fixes': fix_logs,
            })
            operation_manager.write_json(child_id, 'logs/refinador.json', {
                'mode': 'regional_reprocess',
                'backend': refiner_name,
                'fixes': fix_logs,
            })
            operation_manager.write_json(child_id, 'logs/condicionamento.json', {
                'scope': 'regional_identity_only',
                'bundle': repair_bundle.metadata,
                'fixes': [
                    {
                        'index': row.get('index'),
                        'applied': (row.get('backend_metadata') or {}).get('conditioning_applied', []),
                        'fallback': (row.get('backend_metadata') or {}).get('conditioning_fallback'),
                    }
                    for row in fix_logs
                ],
            })
            operation_manager.write_json(child_id, 'logs/tempos.json', {
                'reprocess_ms': total_ms,
                'fixes_ms': [x.get('duration_ms', 0) for x in fix_logs],
                'total_ms': total_ms,
            })
            operation_manager.write_json(child_id, 'logs/erros.json', errors)
            operation_manager.write_json(child_id, 'logs/avaliacao.json', {'approved': None, 'scores': {}, 'notes': ''})

            library_ids = [x.get('id') for x in inherited_refs if x.get('id') in memory_manager.by_id]
            for item_id in library_ids:
                memory_manager.mark_used(item_id)
            memory_manager.register_operation_use(library_ids, child_id)

            operation_manager.finish(
                child_id,
                status='done',
                diagnostic=f'Reprocessamento regional concluído a partir de {parent_operation_id}. {len(fix_logs)} correção(ões) aplicada(s).',
            )
            return {
                'operation_id': child_id,
                'parent_operation_id': parent_operation_id,
                'image': current,
                'fixes': fix_logs,
                'references': inherited_refs,
                'timings': {'reprocess_ms': total_ms, 'total_ms': total_ms},
                'refiner': {'backend': refiner_name, 'mode': 'regional_reprocess'},
                'guide': correction.as_dict(),
            }
        except Exception as exc:
            errors.append({'stage': 'regional_reprocess', 'error': str(exc), 'at': time.time()})
            operation_manager.write_json(child_id, 'logs/erros.json', errors)
            operation_manager.finish(child_id, status='error', diagnostic=str(exc))
            raise


guided_service = GuidedExecutionService()
