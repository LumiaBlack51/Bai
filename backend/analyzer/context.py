"""分析上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(slots=True)
class AnalysisContext:
    source: Path
    translation_unit: "clang.cindex.TranslationUnit"  # type: ignore[name-defined]
    compile_args: List[str]


__all__ = ["AnalysisContext"]

