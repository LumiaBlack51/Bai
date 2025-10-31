"""封装 clang AST 解析。"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .utils import load_clang


class ASTParser:
    """为分析器提供 clang TranslationUnit。"""

    def __init__(self, compile_args: List[str]):
        self.compile_args = compile_args
        self.cindex = load_clang()
        self.index = self.cindex.Index.create()

    def parse(self, source: Path):
        options = self.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
        return self.index.parse(str(source), args=self.compile_args, options=options)


__all__ = ["ASTParser"]

