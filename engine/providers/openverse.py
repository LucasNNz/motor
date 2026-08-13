from __future__ import annotations

from typing import Any
import os
import requests


class OpenverseProvider:
    name = "openverse"
    endpoint = "https://api.openverse.org/v1/images/"

    def search(self, query: str, page_size: int = 20, options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        options = dict(options or {})
        params: dict[str, Any] = {
            'q': query,
            'page_size': max(1, min(int(page_size or 20), 50)),
        }
        # The guide may explicitly control Openverse filters. The previous MVP
        # hard-coded commercial+modification for every search, which made the
        # executor stricter than the guide itself. Keep a derivative-friendly
        # default, but allow the TXT to override it or request all open media.
        license_type = options.get('license_type')
        if license_type not in {None, '', 'none', 'all'}:
            params['license_type'] = str(license_type)
        elif str(license_type).lower() == 'all':
            params['license_type'] = 'all'
        for key in ('license', 'category', 'aspect_ratio', 'size', 'source', 'extension'):
            value = options.get(key)
            if value not in {None, ''}:
                if isinstance(value, (list, tuple)):
                    value = ','.join(str(x) for x in value)
                params[key] = value
        headers = {
            'User-Agent': os.environ.get('CORVO_USER_AGENT', 'CorvoImageEngine/0.12.3 (guided visual reference collector)'),
            'Accept': 'application/json',
        }
        response = requests.get(self.endpoint, params=params, headers=headers, timeout=(3.0, 7.0))
        if not response.ok:
            body = (response.text or '')[:500].replace('\n', ' ')
            raise RuntimeError(f'Openverse HTTP {response.status_code}: {body}')
        payload = response.json()
        results = []
        for raw in payload.get('results', []):
            image_url = raw.get('url') or raw.get('thumbnail')
            if not image_url:
                continue
            results.append({
                'provider': self.name,
                'provider_id': raw.get('id'),
                'title': raw.get('title') or query,
                'author': raw.get('creator'),
                'license': raw.get('license'),
                'license_version': raw.get('license_version'),
                'license_url': raw.get('license_url'),
                'source_url': raw.get('foreign_landing_url') or raw.get('detail_url') or image_url,
                'image_url': image_url,
                'thumbnail_url': raw.get('thumbnail') or image_url,
                'download_urls': [u for u in [
                    (f"https://api.openverse.org/v1/images/{raw.get('id')}/thumb/?full_size=true" if raw.get('id') else None),
                    (f"https://api.openverse.org/v1/images/{raw.get('id')}/thumb/" if raw.get('id') else None),
                    raw.get('thumbnail'),
                    raw.get('url'),
                ] if u],
                'width': raw.get('width'),
                'height': raw.get('height'),
                'category': raw.get('category'),
                'tags': [x.get('name') for x in raw.get('tags', []) if isinstance(x, dict) and x.get('name')],
                'raw': raw,
            })
        return results
