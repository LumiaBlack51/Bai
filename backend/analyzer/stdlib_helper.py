"""标准库使用助手。"""

from __future__ import annotations

from typing import Iterable, List, Sequence

from .base import Checker
from .context import AnalysisContext
from .report import Issue, Suggestion
from .utils import collect_tokens, cursor_location, find_includes, load_clang


REQUIRED_HEADERS = {
    "printf": "stdio.h",
    "scanf": "stdio.h",
    "fprintf": "stdio.h",
    "sprintf": "stdio.h",
    "snprintf": "stdio.h",
    "malloc": "stdlib.h",
    "calloc": "stdlib.h",
    "realloc": "stdlib.h",
    "free": "stdlib.h",
    "memcpy": "string.h",
    "memset": "string.h",
    "strlen": "string.h",
}


PRINTF_SPECIFIERS = set("diuoxXfFeEgGaAcsp")


class StdLibHelperChecker(Checker):
    name = "stdlib-helper"

    def run(self, context: AnalysisContext) -> Iterable[Issue]:
        cindex = load_clang()
        issues: List[Issue] = []

        includes = find_includes(context.translation_unit)

        for node in self._walk(context.translation_unit.cursor, context):
            if node.kind != cindex.CursorKind.CALL_EXPR:
                continue

            callee = self._resolve_callee(node)
            if not callee:
                continue

            header = REQUIRED_HEADERS.get(callee)
            if header and header not in includes:
                issues.append(self._build_include_issue(node, callee, header))

            if callee in {"printf", "scanf"}:
                arguments = list(node.get_arguments())
                if not arguments:
                    continue
                fmt_argument = arguments[0]
                fmt_literal = self._extract_string_literal(fmt_argument)
                if not fmt_literal:
                    continue
                specifiers = self._parse_format_string(fmt_literal)
                value_arguments = arguments[1:]

                if len(value_arguments) != len(specifiers):
                    issues.append(self._build_arg_count_issue(node, callee, len(specifiers), len(value_arguments)))
                elif callee == "scanf":
                    issues.extend(self._check_scanf_arguments(value_arguments))

        return issues

    def _walk(self, cursor, context):
        stack = [cursor]
        while stack:
            current = stack.pop()
            if current.location.file and current.location.file.name != str(context.source):
                continue
            yield current
            stack.extend(list(current.get_children()))

    def _resolve_callee(self, cursor) -> str | None:
        referenced = cursor.referenced
        if referenced and referenced.spelling:
            return referenced.spelling
        name = cursor.spelling or cursor.displayname
        if name:
            return name.split("(")[0]
        return None

    def _build_include_issue(self, cursor, callee: str, header: str) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title=f"在头部加入 `#include <{header}>`",
            detail=f"调用 `{callee}` 需要 `{header}` 提供函数声明。",
        )
        return Issue(
            category="stdlib",
            severity="warning",
            message=f"使用 `{callee}` 时缺少头文件 `<{header}>`。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _extract_string_literal(self, cursor) -> str | None:
        tokens = list(collect_tokens(cursor))
        if not tokens:
            return None
        literal = tokens[0]
        if literal.startswith('"') and literal.endswith('"'):
            return literal.strip('"')
        return None

    def _parse_format_string(self, fmt: str) -> List[str]:
        specifiers: List[str] = []
        i = 0
        while i < len(fmt):
            if fmt[i] == "%":
                i += 1
                if i < len(fmt) and fmt[i] == "%":
                    i += 1
                    continue
                while i < len(fmt) and fmt[i] not in PRINTF_SPECIFIERS:
                    i += 1
                if i < len(fmt):
                    specifiers.append(fmt[i])
                    i += 1
                continue
            i += 1
        return specifiers

    def _build_arg_count_issue(self, cursor, callee: str, expected: int, actual: int) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title="核对格式化字符串与参数数量",
            detail=f"`{callee}` 需要 {expected} 个参数，但当前传入 {actual} 个。",
        )
        return Issue(
            category="stdlib",
            severity="error",
            message=f"`{callee}` 参数数量与格式化字符串不匹配。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _check_scanf_arguments(self, arguments: Sequence["clang.cindex.Cursor"]):  # type: ignore[name-defined]
        issues: List[Issue] = []
        for arg in arguments:
            arg_tokens = list(collect_tokens(arg))
            arg_type = arg.type
            is_pointer = arg_type.kind == load_clang().TypeKind.POINTER
            has_address_of = arg_tokens and arg_tokens[0] == "&"
            if not is_pointer and not has_address_of:
                file_path, line, column = cursor_location(arg)
                issues.append(
                    Issue(
                        category="stdlib",
                        severity="error",
                        message="`scanf` 的参数必须是变量地址或指针。",
                        file=file_path,
                        line=line,
                        column=column,
                        suggestion=Suggestion(
                            title="传入变量地址",
                            detail="示例: `scanf(\"%d\", &value);`",
                        ),
                    )
                )
        return issues


__all__ = ["StdLibHelperChecker"]

