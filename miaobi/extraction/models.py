from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsedElement:
    element_id: str
    element_type: str
    text: str
    structural_path: str
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    filename: str
    content_type: str
    sha256: str
    parser: str
    elements: tuple[ParsedElement, ...]

