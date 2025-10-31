"""检查器基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from .context import AnalysisContext
from .report import Issue


class Checker(ABC):
    name: str

    @abstractmethod
    def run(self, context: AnalysisContext) -> Iterable[Issue]:
        """执行检测。"""


__all__ = ["Checker"]

