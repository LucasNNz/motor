from __future__ import annotations

from typing import Any
import requests


class OpenverseProvider:
    name = "openverse"
    endpoint = "https://api.openverse.org/v1/images/"

    def search(self, query: str, page_size: int = 20) -> list[dict[str, Any]]:
        params = {
            'q': query,
            'page_size': max(1, min(int(page_size or 20), 50)),
            'license_type': 'commercial,modification',
        }
        response = requests.get(self.endpoint, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        results = []
        for raw in payload.get('results', []):
            image_url = raw.get('url') or raw.get('thumbnail')
            if not image_url:
                continue
            results.append({
                'provider': self.name,
                'title': raw.get('title') or query,
                'author': raw.get('creator'),
                'license': raw.get('license'),
                'source_url': raw.get('foreign_landing_url') or raw.get('detail_url') or image_url,
                'image_url': image_url,
                'thumbnail_url': raw.get('thumbnail') or image_url,
                'width': raw.get('width'),
                'height': raw.get('height'),
                'tags': [x.get('name') for x in raw.get('tags', []) if isinstance(x, dict) and x.get('name')],
                'raw': raw,
            })
        return results
