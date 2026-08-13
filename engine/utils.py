from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple
from zipfile import ZipFile, ZIP_DEFLATED
import re


def parse_prompt_lines(text: str) -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    lines = [line.strip() for line in text.splitlines()]
    auto = 1
    for line in lines:
        if not line:
            continue
        if "|" in line:
            left, right = line.split("|", 1)
            item_id = left.strip() or f"{auto:03d}"
            prompt = right.strip()
        else:
            item_id = f"{auto:03d}"
            prompt = line
        if not prompt:
            continue
        item_id = sanitize_file_stem(item_id)
        items.append((item_id, prompt))
        auto += 1
    return items


def sanitize_file_stem(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value or "item"


def build_zip(source_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file() and path != zip_path:
                zf.write(path, path.relative_to(source_dir))
