"""后端配置模块。

提供 Analyzer 运行时需要的可配置项，例如 clang 编译参数、日志开关等。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(slots=True)
class AnalyzerConfig:
    """分析器运行配置。"""

    compile_args: List[str] = field(default_factory=lambda: ["-std=c11"])
    enable_suggestions: bool = True
    stop_on_error: bool = False


DEFAULT_CONFIG = AnalyzerConfig()

__all__ = ["AnalyzerConfig", "DEFAULT_CONFIG"]

