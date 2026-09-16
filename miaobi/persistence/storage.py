from __future__ import annotations

from pathlib import Path

from miaobi.config import get_settings


def save_source_file(*, project_id: str, run_id: str, filename: str, data: bytes) -> str:
    safe_name = Path(filename).name or "untitled"
    root = Path(get_settings().storage_root).resolve()
    target_dir = root / project_id / run_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name
    target.write_bytes(data)
    return str(target.relative_to(root))
