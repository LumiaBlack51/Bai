"""报告与数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


Severity = str


@dataclass(slots=True)
class Suggestion:
    title: str
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        data: Dict[str, str] = {"title": self.title}
        if self.detail:
            data["detail"] = self.detail
        return data


@dataclass(slots=True)
class Issue:
    category: str
    severity: Severity
    message: str
    file: Path
    line: int
    column: Optional[int] = None
    suggestion: Optional[Suggestion] = None

    def to_dict(self) -> Dict[str, object]:
        data: Dict[str, object] = {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "file": str(self.file),
            "line": self.line,
        }
        if self.column is not None:
            data["column"] = self.column
        if self.suggestion:
            data["suggestion"] = self.suggestion.to_dict()
        return data


class Report:
    """单个源文件的检测报告。"""

    def __init__(self, source: Path, issues: Iterable[Issue]):
        self.source = source
        self.issues: List[Issue] = list(issues)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    def severity_summary(self) -> Dict[Severity, int]:
        summary: Dict[Severity, int] = {}
        for issue in self.issues:
            summary[issue.severity] = summary.get(issue.severity, 0) + 1
        return summary

    def to_dict(self) -> Dict[str, object]:
        return {
            "source": str(self.source),
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": self.severity_summary(),
        }

    def format_text(self) -> str:
        lines: List[str] = []
        lines.append(f"文件: {self.source}")
        summary = self.severity_summary()
        if summary:
            summary_text = ", ".join(f"{k}={v}" for k, v in sorted(summary.items()))
        else:
            summary_text = "无问题"
        lines.append(f"统计: {summary_text}")
        if not self.issues:
            lines.append("  ✅ 未检测到问题")
            return "\n".join(lines)

        for issue in self.issues:
            location = f"{issue.file}:{issue.line}"
            if issue.column is not None:
                location += f":{issue.column}"
            lines.append(f"  [{issue.severity.upper()}][{issue.category}] {location}: {issue.message}")
            if issue.suggestion:
                lines.append(f"    ↳ 建议: {issue.suggestion.title}")
                if issue.suggestion.detail:
                    detail_lines = issue.suggestion.detail.strip().splitlines()
                    for detail in detail_lines:
                        lines.append(f"       {detail}")
        return "\n".join(lines)


__all__ = ["Issue", "Report", "Severity", "Suggestion"]

