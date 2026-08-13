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
    def _filter_config(self, guide: ParsedGuide) -> dict[str, Any]:
        return dict(guide.first('FILTER') or {})

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
            ('character', scene.get('visual_reference') or scene.get('subject'), 'reference_target'),
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

    def collect_from_guide(self, guide_text: str, *, providers: list[str], auto_approve: bool = False) -> dict[str, Any]:
        guide = guide_parser.parse(guide_text)
        filters = self._filter_config(guide)
        results = []
        for spec in self._all_search_specs(guide):
            section = spec['section']; block = spec['block']
            result = collector_service.collect(
                query=spec['query'], type_name=spec['type'], concept=spec['concept'], providers=providers,
                per_provider=min(50, max(8, spec['collect_limit'] // max(1, len(providers)))),
                save_limit=spec['keep_limit'], keep_limit=spec['keep_limit'], collect_limit=spec['collect_limit'],
                auto_approve=auto_approve, filters=filters, search_metadata={'section': section, **block},
            )
            results.append({'spec': spec, 'result': result})
        composer_engine.reload_memory()
        return {'guide': guide.as_dict(), 'filters': filters, 'results': results, 'memory': memory_manager.status()}

    def _should_collect(self, guide: ParsedGuide) -> bool:
        for spec in self._all_search_specs(guide):
            if not memory_manager.search_best(spec['concept'], spec['type'], limit=1, approved_only=True):
                return True
        return False

    def _selected_references(self, guide: ParsedGuide, composition: dict[str, Any]) -> list[dict[str, Any]]:
        refs: dict[str, dict[str, Any]] = {}
        plan = (composition or {}).get('plan') or {}
        for label in ['background', 'pose', 'face', 'outfit', 'object']:
            item = plan.get(label) or {}
            item_id = item.get('id')
            if item_id:
                refs[f'composer_{label}'] = {'label': f'composer_{label}', 'id': item_id, 'source': item.get('source'), 'file': item.get('file')}
        for spec in self._all_search_specs(guide):
            found = memory_manager.search_best(spec['concept'], spec['type'], limit=1, approved_only=True)
            if found:
                item = found[0]
                refs[f"guide_{spec['type']}"] = {
                    'label': f"guide_{spec['type']}", 'id': item['id'], 'source': item.get('source'),
                    'file': item.get('local_path'), 'concept': item.get('concept'), 'query': spec['query'],
                    'preferred': item.get('preferred'), 'success_rate': item.get('success_rate', 0),
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
                auto_approve_collected: bool = False) -> dict[str, Any]:
        guide = guide_parser.parse(guide_text)
        operation_id = operation_manager.create(prompt=prompt, guide_text=guide_text)
        started = time.perf_counter()
        search_log: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        try:
            if collect_missing and self._should_collect(guide):
                collect_started = time.perf_counter()
                collected = self.collect_from_guide(guide_text, providers=['openverse', 'wikimedia_commons'], auto_approve=auto_approve_collected)
                search_log = collected['results']
                collect_ms = int((time.perf_counter() - collect_started) * 1000)
            else:
                collect_ms = 0
                for spec in self._all_search_specs(guide):
                    found = memory_manager.search_best(spec['concept'], spec['type'], limit=10, approved_only=True)
                    search_log.append({'spec': spec, 'library_matches': [x['id'] for x in found]})

            compose_started = time.perf_counter()
            base = composer_engine.generate_guided(guide, width, height)
            composer_ms = int((time.perf_counter() - compose_started) * 1000)
            composition = composer_engine.last_info
            operation_manager.save_image(operation_id, 'etapas/composicao_base.png', base)
            operation_manager.save_image(operation_id, 'etapas/antes_refinamento.png', base)

            references = self._selected_references(guide, composition)
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
                'refiner': refiner_log, 'guide': guide.as_dict(),
            }
        except Exception as exc:
            errors.append({'stage': 'guided_execution', 'error': str(exc), 'at': time.time()})
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
