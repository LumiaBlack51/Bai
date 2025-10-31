"""数值与控制流检查。"""

from __future__ import annotations

import re

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
        if not self._is_reachable(cursor):
            return []

        tokens = list(collect_tokens(cursor))
        text = "".join(tokens)
        if self._loop_is_definitely_infinite(cursor, tokens=tokens, text=text):
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

    def _is_reachable(self, cursor) -> bool:
        cindex = load_clang()
        parent = cursor.semantic_parent
        if not parent:
            return True

        siblings = list(parent.get_children())
        for child in siblings:
            if child == cursor:
                return True
            if child.location.file and child.location.file != cursor.location.file:
                continue
            if child.kind in {cindex.CursorKind.RETURN_STMT, cindex.CursorKind.BREAK_STMT}:
                return False
            if child.kind in {cindex.CursorKind.WHILE_STMT, cindex.CursorKind.FOR_STMT}:
                tokens = list(collect_tokens(child))
                text = "".join(tokens)
                if self._loop_is_definitely_infinite(child, tokens=tokens, text=text):
                    return False
        return True

    def _loop_is_definitely_infinite(self, cursor, *, tokens=None, text: str | None = None) -> bool:
        cindex = load_clang()
        tokens = tokens or list(collect_tokens(cursor))
        text = text if text is not None else "".join(tokens)

        if cursor.kind == cindex.CursorKind.WHILE_STMT:
            condition_cursor, body_cursor = self._split_while_children(cursor)
            condition_text = "".join(collect_tokens(condition_cursor)) if condition_cursor else ""
            condition_clean = condition_text.replace(" ", "")
            if condition_clean in {"1", "(1)", "true", "(true)"}:
                return True

            simple_var = self._extract_condition_variable(condition_text)
            if simple_var and not self._variable_modified(body_cursor, simple_var):
                return True

            relational_match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(<=|>=|<|>)\s*(.+)", condition_clean)
            if relational_match:
                var = relational_match.group(1)
                if not self._variable_modified(body_cursor, var):
                    return True
            return False

        if cursor.kind == cindex.CursorKind.FOR_STMT:
            init_cursor, cond_cursor, inc_cursor, body_cursor = self._split_for_children(cursor)
            cond_text = "".join(collect_tokens(cond_cursor)) if cond_cursor else ""
            cond_clean = cond_text.replace(" ", "")
            if not cond_clean:
                return True
            if cond_clean in {"1", "true"}:
                return True
            if "!=" in cond_clean or "==" in cond_clean:
                return True

            relational_match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(<=|>=|<|>)\s*(.+)", cond_clean)
            if relational_match:
                var, op, _ = relational_match.groups()
                direction = self._analyze_increment(var, inc_cursor)
                if direction == "none":
                    return True
                if direction == "up" and op in {">", ">="}:
                    return True
                if direction == "down" and op in {"<", "<="}:
                    return True
            return False

        return False

    def _split_while_children(self, cursor):
        cindex = load_clang()
        condition = None
        body = None
        for child in cursor.get_children():
            if child.kind == cindex.CursorKind.COMPOUND_STMT:
                body = child
            elif condition is None:
                condition = child
        return condition, body

    def _split_for_children(self, cursor):
        cindex = load_clang()
        init = None
        condition = None
        increment = None
        body = None
        for child in cursor.get_children():
            if child.kind == cindex.CursorKind.COMPOUND_STMT:
                body = child
            elif init is None:
                init = child
            elif condition is None:
                condition = child
            elif increment is None:
                increment = child
        return init, condition, increment, body

    def _extract_condition_variable(self, condition_text: str) -> str | None:
        if not condition_text:
            return None
        text = condition_text.strip()
        match = re.match(r"\(?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)?", text)
        if not match:
            return None
        symbol = match.group(1)
        if re.search(r"[<>=]", text):
            return None
        if "!=" in text and "0" not in text:
            return None
        return symbol

    def _variable_modified(self, body_cursor, var: str) -> bool:
        if body_cursor is None:
            return False
        tokens = list(collect_tokens(body_cursor))
        if not tokens:
            return False
        text = " ".join(tokens)

        continue_index = text.find("continue")

        inc_pattern = re.compile(rf"(\+\+\s*{var}|{var}\s*\+\+)" )
        match = inc_pattern.search(text)
        if match and (continue_index == -1 or match.start() < continue_index):
            return True

        dec_pattern = re.compile(rf"(--\s*{var}|{var}\s*--)" )
        match = dec_pattern.search(text)
        if match and (continue_index == -1 or match.start() < continue_index):
            return True

        compound_pattern = re.compile(rf"{var}\s*([+\-*/]=)\s*([^;]+)")
        for match in compound_pattern.finditer(text):
            if continue_index != -1 and match.start() > continue_index:
                continue
            op = match.group(1)
            rhs = match.group(2).strip()
            if op in {"+=", "-=", "*=", "/="}:
                if rhs in {"0", "0.0", "0f", "0F"} and op in {"+=", "-=", "*=", "/="}:
                    continue
            return True

        assign_pattern = re.compile(rf"{var}\s*=\s*([^;]+)")
        for match in assign_pattern.finditer(text):
            if continue_index != -1 and match.start() > continue_index:
                continue
            rhs = match.group(1).strip()
            rhs = rhs.split(";")[0].strip()
            if rhs in {var, f"({var})"}:
                continue
            return True

        return False

    def _analyze_increment(self, var: str, increment_cursor) -> str:
        increment_text = "".join(collect_tokens(increment_cursor)) if increment_cursor else ""
        if not increment_text:
            return "none"

        if re.search(rf"(\+\+\s*{var}|{var}\s*\+\+)", increment_text):
            return "up"
        if re.search(rf"(--\s*{var}|{var}\s*--)", increment_text):
            return "down"

        compound_match = re.search(rf"{var}\s*([+\-]=)\s*([^;]+)", increment_text)
        if compound_match:
            op = compound_match.group(1)
            rhs = compound_match.group(2).strip()
            if rhs.startswith("-"):
                return "down" if op == "+=" else "up"
            return "up" if op == "+=" else "down"

        assign_match = re.search(rf"{var}\s*=\s*{var}\s*([+\-])\s*([^;]+)", increment_text)
        if assign_match:
            sign = assign_match.group(1)
            rhs = assign_match.group(2).strip()
            if rhs.startswith("-"):
                return "down" if sign == "+" else "up"
            return "up" if sign == "+" else "down"

        return "none"

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

