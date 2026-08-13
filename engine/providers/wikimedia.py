from __future__ import annotations

from typing import Any
import requests


class WikimediaCommonsProvider:
    name = "wikimedia_commons"
    endpoint = "https://commons.wikimedia.org/w/api.php"

    def search(self, query: str, page_size: int = 20) -> list[dict[str, Any]]:
        params = {
            'action': 'query',
            'format': 'json',
            'generator': 'search',
            'gsrsearch': query,
            'gsrnamespace': 6,
            'gsrlimit': max(1, min(int(page_size or 20), 50)),
            'prop': 'imageinfo|info',
            'iiprop': 'url|size|mime|extmetadata',
            'inprop': 'url',
            'origin': '*',
        }
        response = requests.get(self.endpoint, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        pages = (payload.get('query') or {}).get('pages') or {}
        results = []
        for page in pages.values():
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
            author = None
            if isinstance(meta.get('Artist'), dict):
                author = meta['Artist'].get('value')
            license_name = None
            if isinstance(meta.get('LicenseShortName'), dict):
                license_name = meta['LicenseShortName'].get('value')
            results.append({
                'provider': self.name,
                'title': page.get('title'),
                'author': author,
                'license': license_name,
                'source_url': page.get('fullurl') or image_url,
                'image_url': image_url,
                'thumbnail_url': image_url,
                'width': info.get('width'),
                'height': info.get('height'),
                'tags': tags,
                'raw': page,
            })
        return results
