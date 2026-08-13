from __future__ import annotations

from typing import Any
import os
import requests


class WikimediaCommonsProvider:
    name = "wikimedia_commons"
    endpoint = "https://commons.wikimedia.org/w/api.php"

    def search(self, query: str, page_size: int = 20, options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        options = dict(options or {})
        params = {
            'action': 'query',
            'format': 'json',
            'formatversion': 2,
            'generator': 'search',
            'gsrsearch': query,
            'gsrnamespace': 6,
            'gsrlimit': max(1, min(int(page_size or 20), 50)),
            'prop': 'imageinfo|info',
            'iiprop': 'url|size|mime|extmetadata',
            'inprop': 'url',
        }
        # Wikimedia requires an identifying User-Agent for API clients.
        ua = os.environ.get('CORVO_USER_AGENT', 'CorvoImageEngine/0.13 (guided visual reference collector)')
        headers = {
            'User-Agent': ua,
            'Api-User-Agent': ua,
            'Accept': 'application/json',
        }
        response = requests.get(self.endpoint, params=params, headers=headers, timeout=60)
        response.raise_for_status()
        payload = response.json()
        pages = (payload.get('query') or {}).get('pages') or []
        if isinstance(pages, dict):
            pages = list(pages.values())
        results = []
        for page in pages:
            infos = page.get('imageinfo') or []
            if not infos:
                continue
            info = infos[0]
            meta = info.get('extmetadata') or {}
            image_url = info.get('url')
            if not image_url:
                continue
            tags = []
            cats = meta.get('Categories', {}) if isinstance(meta.get('Categories'), dict) else {}
            cat_val = cats.get('value') if isinstance(cats, dict) else None
            if cat_val:
                tags.extend([x.strip() for x in str(cat_val).split('|') if x.strip()])
            author = meta.get('Artist', {}).get('value') if isinstance(meta.get('Artist'), dict) else None
            license_name = meta.get('LicenseShortName', {}).get('value') if isinstance(meta.get('LicenseShortName'), dict) else None
            license_url = meta.get('LicenseUrl', {}).get('value') if isinstance(meta.get('LicenseUrl'), dict) else None
            results.append({
                'provider': self.name,
                'title': page.get('title'),
                'author': author,
                'license': license_name,
                'license_url': license_url,
                'source_url': page.get('fullurl') or image_url,
                'image_url': image_url,
                'thumbnail_url': image_url,
                'width': info.get('width'),
                'height': info.get('height'),
                'tags': tags,
                'raw': page,
            })
        return results
