from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


def _coerce(value: str) -> Any:
    v = value.strip()
    low = v.lower()
    if low in {"true", "yes", "sim", "on"}:
        return True
    if low in {"false", "no", "nao", "não", "off"}:
        return False
    if low in {"none", "null", "-"}:
        return None
    if re.fullmatch(r"-?\d+", v):
        try:
            return int(v)
        except Exception:
            pass
    if re.fullmatch(r"-?\d+(?:\.\d+)?%", v):
        try:
            return float(v[:-1]) / 100.0
        except Exception:
            pass
    if re.fullmatch(r"-?\d+\.\d+", v):
        try:
            return float(v)
        except Exception:
            pass
    if "," in v:
        return [x.strip() for x in v.split(",") if x.strip()]
    return v


@dataclass
class ParsedGuide:
    raw: str
    sections: dict[str, list[dict[str, Any]]]

    def first(self, name: str) -> dict[str, Any]:
        rows = self.sections.get(name.upper()) or []
        return rows[0] if rows else {}

    def all(self, name: str) -> list[dict[str, Any]]:
        return list(self.sections.get(name.upper()) or [])

    def as_dict(self) -> dict[str, Any]:
        return {"sections": self.sections}

    def search_blocks(self) -> list[tuple[str, dict[str, Any]]]:
        out: list[tuple[str, dict[str, Any]]] = []
        for name, rows in self.sections.items():
            if name.startswith("SEARCH_"):
                for row in rows:
                    out.append((name, row))

        # Compatibility with human-readable guides that place the component name
        # before SEARCH. Normalize them into the Engine's canonical contract.
        aliases = {
            'SUBJECT_SEARCH': ('SEARCH_CHARACTER', 'SUBJECT', 'reference_target', 'concept'),
            'BACKGROUND_SEARCH': ('SEARCH_BACKGROUND', 'BACKGROUND', 'environment', 'concept'),
            'POSE_SEARCH': ('SEARCH_POSE', 'SUBJECT', 'pose', 'pose'),
        }
        existing = {name for name, _ in out}
        for source_name, (target_name, context_name, concept_key, context_key) in aliases.items():
            if target_name in existing:
                continue
            context = self.first(context_name)
            for row in self.all(source_name):
                block = dict(row)
                queries = block.get('queries')
                if isinstance(queries, str):
                    queries = [queries]
                if isinstance(queries, (list, tuple)) and queries:
                    block.setdefault('query', str(queries[0]))
                    if len(queries) > 1:
                        block.setdefault('fallback_queries', [str(x) for x in queries[1:]])
                if block.get('search_required') is not None:
                    block.setdefault('required', block.get('search_required'))
                if block.get('preferred_sources') is not None:
                    block.setdefault('providers', block.get('preferred_sources'))
                if context.get(context_key):
                    block.setdefault(concept_key, context.get(context_key))
                out.append((target_name, block))
        return out


class GuideParser:
    SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")

    def parse(self, text: str) -> ParsedGuide:
        sections: dict[str, list[dict[str, Any]]] = {}
        current: dict[str, Any] | None = None
        current_name: str | None = None
        pending_key: str | None = None
        for raw_line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            match = self.SECTION_RE.match(line)
            if match:
                current_name = match.group(1).strip().upper()
                current = {}
                pending_key = None
                sections.setdefault(current_name, []).append(current)
                continue
            if current is None or current_name is None:
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip().lower()
                if value.strip() == '':
                    current[key] = []
                    pending_key = key
                else:
                    current[key] = _coerce(value)
                    pending_key = None
            else:
                if pending_key:
                    current.setdefault(pending_key, []).append(line)
                else:
                    current.setdefault("_lines", []).append(line)
        return ParsedGuide(raw=text or "", sections=sections)


TYPE_BY_SEARCH_SECTION = {
    "SEARCH_CHARACTER": "character",
    "SEARCH_POSE": "pose",
    "SEARCH_FACE": "face",
    "SEARCH_EXPRESSION": "expression",
    "SEARCH_CLOTHES": "clothes",
    "SEARCH_OUTFIT": "outfit",
    "SEARCH_BACKGROUND": "background",
    "SEARCH_OBJECT": "object",
    "SEARCH_LIGHTING": "lighting",
    "SEARCH_CAMERA": "camera",
    "SEARCH_WEATHER": "weather",
    "SEARCH_TEXTURE": "texture",
    "SEARCH_STYLE": "style",
    "SEARCH_COMPOSITION": "composition",
}


guide_parser = GuideParser()
