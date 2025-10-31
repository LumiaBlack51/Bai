"""变量使用检查。"""

from __future__ import annotations

from typing import Iterable, List, Set

from .base import Checker
from .context import AnalysisContext
from .report import Issue, Suggestion
from .utils import collect_tokens, cursor_location, iter_children, load_clang


class VariableUsageChecker(Checker):
    name = "variable-usage"

    def run(self, context: AnalysisContext) -> Iterable[Issue]:
        cindex = load_clang()
        issues: List[Issue] = []

        for cursor in context.translation_unit.cursor.get_children():
            if cursor.location.file and cursor.location.file.name != str(context.source):
                continue

            if cursor.kind == cindex.CursorKind.VAR_DECL:
                issues.extend(self._check_var_decl(cursor))
            elif cursor.kind == cindex.CursorKind.FUNCTION_DECL:
                issues.extend(self._check_function(cursor))

        return issues

    def _check_var_decl(self, cursor) -> Iterable[Issue]:
        if cursor.storage_class == load_clang().StorageClass.EXTERN:
            return []

        if list(cursor.get_children()):
            return []

        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title=f"在声明 `{cursor.spelling}` 时完成初始化",
            detail="例如: `int value = 0;` 或在首次使用前显式赋值。",
        )
        return [
            Issue(
                category="variable",
                severity="warning",
                message=f"变量 `{cursor.spelling}` 在使用前可能未初始化。",
                file=file_path,
                line=line,
                column=column,
                suggestion=suggestion,
            )
        ]

    def _check_function(self, cursor) -> Iterable[Issue]:
        cindex = load_clang()
        assigned: Set[str] = set()
        reported: Set[str] = set()
        issues: List[Issue] = []

        for param in cursor.get_arguments() or []:
            if param.spelling:
                assigned.add(param.spelling)

        for node in self._walk(cursor):
            if node.kind == cindex.CursorKind.VAR_DECL and node.spelling:
                has_initializer = any(True for _ in node.get_children())
                if has_initializer:
                    assigned.add(node.spelling)

            if node.kind == cindex.CursorKind.BINARY_OPERATOR:
                children = list(node.get_children())
                if children:
                    left = children[0]
                    if left.kind == cindex.CursorKind.DECL_REF_EXPR and left.spelling:
                        ref = left.referenced
                        if ref and ref.kind == cindex.CursorKind.VAR_DECL:
                            assigned.add(left.spelling)

            if node.kind == cindex.CursorKind.DECL_REF_EXPR:
                ref = node.referenced
                if not ref or ref.kind != cindex.CursorKind.VAR_DECL:
                    continue

                name = node.spelling
                if not name or name in assigned or name in reported:
                    continue

                file_path, line, column = cursor_location(node)
                issues.append(
                    Issue(
                        category="variable",
                        severity="warning",
                        message=f"变量 `{name}` 可能在赋值前被使用。",
                        file=file_path,
                        line=line,
                        column=column,
                        suggestion=Suggestion(
                            title="在引用前检查变量赋值路径",
                            detail="可以通过初始化或在所有分支赋值来避免。",
                        ),
                    )
                )
                reported.add(name)

        return issues

    def _walk(self, cursor):
        yield cursor
        for child in iter_children(cursor):
            yield from self._walk(child)


__all__ = ["VariableUsageChecker"]

