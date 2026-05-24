from __future__ import annotations

import json
from pathlib import Path


def load_parse_ready_files(manifest_path: Path) -> list[Path]:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    items = payload.get("parse_ready_files", [])

    discovered_paths: list[Path] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_path = item.get("path")
        if not raw_path:
            continue

        candidate = Path(str(raw_path)).expanduser()
        resolved = candidate.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        discovered_paths.append(resolved)

    return discovered_paths
