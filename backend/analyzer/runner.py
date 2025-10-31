"""分析器运行入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from ..config import AnalyzerConfig, DEFAULT_CONFIG
from .ast_parser import ASTParser
from .base import Checker
from .context import AnalysisContext
from .memory_checker import MemorySafetyChecker
from .numeric_control_checker import NumericControlChecker
from .report import Issue, Report
from .stdlib_helper import StdLibHelperChecker
from .variable_checker import VariableUsageChecker


class AnalyzerRunner:
    def __init__(self, config: AnalyzerConfig | None = None):
        self.config = config or DEFAULT_CONFIG
        self.parser = ASTParser(self.config.compile_args)
        self.checkers: List[Checker] = [
            MemorySafetyChecker(),
            VariableUsageChecker(),
            StdLibHelperChecker(),
            NumericControlChecker(),
        ]

    def analyze(self, source: Path) -> Report:
        try:
            translation_unit = self.parser.parse(source)
        except Exception as exc:
            issue = Issue(
                category="infrastructure",
                severity="error",
                message=f"解析源码时出错: {exc}",
                file=source,
                line=0,
                column=None,
                suggestion=None,
            )
            return Report(source, [issue])

        context = AnalysisContext(
            source=source,
            translation_unit=translation_unit,
            compile_args=self.config.compile_args,
        )

        issues: List[Issue] = []
        for checker in self.checkers:
            issues.extend(checker.run(context))
            if self.config.stop_on_error and any(issue.severity == "error" for issue in issues):
                break

        issues.sort(key=_issue_sort_key)
        return Report(source, issues)


def _issue_sort_key(issue: Issue):
    severity_rank = {"error": 0, "warning": 1, "info": 2}
    return (
        severity_rank.get(issue.severity, 3),
        str(issue.file),
        issue.line,
        issue.column or 0,
    )


__all__ = ["AnalyzerRunner"]

