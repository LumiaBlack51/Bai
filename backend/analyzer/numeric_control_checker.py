"""数值与控制流检查。"""

from __future__ import annotations

from typing import Iterable, List

from .base import Checker
from .context import AnalysisContext
from .report import Issue, Suggestion
from .utils import collect_tokens, cursor_location, iter_children, load_clang


class NumericControlChecker(Checker):
    name = "numeric-control"

    def run(self, context: AnalysisContext) -> Iterable[Issue]:
        cindex = load_clang()
        issues: List[Issue] = []

        for node in self._walk(context.translation_unit.cursor, context):
            if node.kind == cindex.CursorKind.BINARY_OPERATOR:
                issues.extend(self._check_division(node))
            elif node.kind in {cindex.CursorKind.WHILE_STMT, cindex.CursorKind.FOR_STMT}:
                issues.extend(self._check_loop(node))
            elif node.kind == cindex.CursorKind.COMPOUND_STMT:
                issues.extend(self._check_unreachable(node))

        return issues

    def _walk(self, cursor, context):
        stack = [cursor]
        while stack:
            current = stack.pop()
            if current.location.file and current.location.file.name != str(context.source):
                continue
            yield current
            stack.extend(list(current.get_children()))

    def _check_division(self, cursor) -> Iterable[Issue]:
        tokens = list(collect_tokens(cursor))
        if "/" not in tokens:
            return []
        slash_index = tokens.index("/")
        if slash_index + 1 < len(tokens) and tokens[slash_index + 1] == "0":
            file_path, line, column = cursor_location(cursor)
            suggestion = Suggestion(
                title="在执行除法前检查分母",
                detail="如果分母可能为 0，可提前返回或抛出错误。",
            )
            return [
                Issue(
                    category="numeric",
                    severity="error",
                    message="检测到除以 0 的风险。",
                    file=file_path,
                    line=line,
                    column=column,
                    suggestion=suggestion,
                )
            ]
        return []

    def _check_loop(self, cursor) -> Iterable[Issue]:
        tokens = list(collect_tokens(cursor))
        text = "".join(tokens)
        if cursor.kind == load_clang().CursorKind.WHILE_STMT and "while" in tokens:
            if "(1)" in text or "(true)" in text:
                return [self._build_loop_issue(cursor)]
        if cursor.kind == load_clang().CursorKind.FOR_STMT and text.startswith("for(;;"):
            return [self._build_loop_issue(cursor)]
        return []

    def _build_loop_issue(self, cursor) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title="为循环添加退出条件或 break",
            detail="确保循环条件可以变为假，或在循环体内加入跳出逻辑。",
        )
        return Issue(
            category="control-flow",
            severity="warning",
            message="循环条件恒为真，可能导致死循环。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _check_unreachable(self, cursor) -> Iterable[Issue]:
        children = list(iter_children(cursor))
        issues: List[Issue] = []
        encountered_terminal = False
        for child in children:
            if encountered_terminal:
                file_path, line, column = cursor_location(child)
                issues.append(
                    Issue(
                        category="control-flow",
                        severity="warning",
                        message="存在不可达代码段。",
                        file=file_path,
                        line=line,
                        column=column,
                        suggestion=Suggestion(
                            title="删除或移动不可达代码",
                            detail="如果需要执行，请调整控制流以确保执行到。",
                        ),
                    )
                )
                break

            if child.kind in {
                load_clang().CursorKind.RETURN_STMT,
                load_clang().CursorKind.BREAK_STMT,
                load_clang().CursorKind.CONTINUE_STMT,
            }:
                encountered_terminal = True
        return issues


__all__ = ["NumericControlChecker"]

