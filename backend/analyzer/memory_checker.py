"""内存安全检查。"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from .base import Checker
from .context import AnalysisContext
from .report import Issue, Suggestion
from .utils import collect_tokens, cursor_location, iter_children, load_clang


class MemorySafetyChecker(Checker):
    name = "memory-safety"

    def __init__(self) -> None:
        self._global_uninitialized: Set[str] = set()
        self._global_array_sizes: Dict[str, int] = {}

    def run(self, context: AnalysisContext) -> Iterable[Issue]:
        cindex = load_clang()
        issues: List[Issue] = []

        self._global_uninitialized.clear()
        self._global_array_sizes.clear()

        for cursor in context.translation_unit.cursor.get_children():
            if cursor.location.file and cursor.location.file.name != str(context.source):
                continue

            if cursor.kind == cindex.CursorKind.VAR_DECL:
                issues.extend(self._check_pointer_initialization(cursor))
                self._collect_global_array(cursor)
            elif cursor.kind == cindex.CursorKind.FUNCTION_DECL:
                issues.extend(self._check_function(cursor))

        return issues

    def _check_pointer_initialization(self, cursor) -> Iterable[Issue]:
        cindex = load_clang()
        if cursor.type.kind != cindex.TypeKind.POINTER:
            return []

        initialized = any(True for _ in cursor.get_children())
        if initialized:
            return []

        if cursor.spelling:
            self._global_uninitialized.add(cursor.spelling)

        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title="在声明时初始化指针或在首次使用前赋值",
            detail="例如: `int *ptr = NULL;` 并确保使用前检查是否为空。",
        )
        return [
            Issue(
                category="memory",
                severity="warning",
                message=f"指针 `{cursor.spelling}` 未初始化，可能导致悬空或野指针。",
                file=file_path,
                line=line,
                column=column,
                suggestion=suggestion,
            )
        ]

    def _check_function(self, cursor) -> Iterable[Issue]:
        issues: List[Issue] = []
        pointer_null: Set[str] = set()
        allocation_calls = 0
        free_calls = 0

        local_uninitialized: Set[str] = set()
        pointer_vars: Set[str] = set()
        array_sizes: Dict[str, int] = dict(self._global_array_sizes)
        for param in cursor.get_arguments() or []:
            if param.type.kind == load_clang().TypeKind.POINTER and param.spelling:
                pointer_vars.add(param.spelling)

        for child in cursor.get_children():
            if child.kind == load_clang().CursorKind.PARM_DECL:
                if child.type.kind == load_clang().TypeKind.POINTER and child.spelling:
                    pointer_vars.add(child.spelling)
                continue
            if child.kind == load_clang().CursorKind.VAR_DECL and child.type.kind == load_clang().TypeKind.POINTER:
                if child.spelling:
                    pointer_vars.add(child.spelling)
                init_children = list(child.get_children())
                if not init_children:
                    if child.spelling:
                        local_uninitialized.add(child.spelling)
                else:
                    init_tokens = list(collect_tokens(child))
                    if child.spelling and ("NULL" in init_tokens or init_tokens[-1] == "0"):
                        pointer_null.add(child.spelling)
            elif child.kind == load_clang().CursorKind.VAR_DECL and child.type.kind == load_clang().TypeKind.CONSTANTARRAY:
                size = self._extract_array_size(child.type)
                if child.spelling and size is not None:
                    array_sizes[child.spelling] = size

        for node in self._walk(cursor):
            tokens = list(collect_tokens(node))
            if not tokens:
                continue

            # 空指针赋值追踪
            if "=" in tokens and ("NULL" in tokens or tokens[-1] == "0"):
                eq_index = tokens.index("=")
                target = tokens[eq_index - 1] if eq_index > 0 else None
                if target and target in pointer_vars:
                    pointer_null.add(target)
            elif "=" in tokens:
                eq_index = tokens.index("=")
                target = tokens[eq_index - 1] if eq_index > 0 else None
                if target and target in local_uninitialized:
                    local_uninitialized.discard(target)

            if node.kind == load_clang().CursorKind.DECL_REF_EXPR:
                name = node.spelling
                if name and name in (local_uninitialized | self._global_uninitialized):
                    issues.append(self._build_uninitialized_pointer_issue(node, name))
                    local_uninitialized.discard(name)

            # 统计 malloc/free 调用
            if node.kind == load_clang().CursorKind.CALL_EXPR:
                callee = node.displayname.split("(")[0]
                if callee in {"malloc", "calloc", "realloc"}:
                    allocation_calls += 1
                elif callee == "free":
                    free_calls += 1

            # 检测悬空指针使用
            if node.kind == load_clang().CursorKind.UNARY_OPERATOR and tokens[0] == "*":
                name = tokens[1] if len(tokens) > 1 else None
                if name and name in pointer_null:
                    issues.append(self._build_null_deref_issue(node, name))

            if node.kind == load_clang().CursorKind.BINARY_OPERATOR and tokens and tokens[0] == "*":
                name = tokens[1] if len(tokens) > 1 else None
                if name and name in pointer_null:
                    issues.append(self._build_null_deref_issue(node, name))

            # 函数调用时传递可能为空的指针
            if node.kind == load_clang().CursorKind.CALL_EXPR:
                for argument in node.get_arguments():
                    arg_tokens = list(collect_tokens(argument))
                    for tok in arg_tokens:
                        if tok in pointer_null:
                            issues.append(self._build_null_call_issue(argument, tok))

            if node.kind == load_clang().CursorKind.ARRAY_SUBSCRIPT_EXPR:
                array_issue = self._check_array_bounds(node, array_sizes)
                if array_issue:
                    issues.append(array_issue)

        if allocation_calls > free_calls:
            issues.append(self._build_leak_issue(cursor, allocation_calls, free_calls))

        return issues

    def _walk(self, cursor):
        yield cursor
        for child in iter_children(cursor):
            yield from self._walk(child)

    def _build_null_deref_issue(self, cursor, name: str) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title=f"在解引用 `{name}` 前检查是否为空",
            detail="例如: `if ({0} == NULL) {{ /* 错误处理 */ }}`".format(name),
        )
        return Issue(
            category="memory",
            severity="error",
            message=f"指针 `{name}` 可能为空却被解引用。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _build_null_call_issue(self, cursor, name: str) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title="在传入指针参数前进行空指针检查",
            detail=f"确保 `{name}` 在调用前已经被赋值为有效地址。",
        )
        return Issue(
            category="memory",
            severity="warning",
            message=f"指针 `{name}` 可能为空却被作为参数传递。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _build_uninitialized_pointer_issue(self, cursor, name: str) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title=f"在使用 `{name}` 前赋值有效地址",
            detail="例如将其指向现有变量或动态分配的内存。",
        )
        return Issue(
            category="memory",
            severity="error",
            message=f"指针 `{name}` 可能未初始化却被使用。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _build_leak_issue(self, cursor, allocs: int, frees: int) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title="为每一次动态分配配对调用 free",
            detail="考虑使用 goto/清理块或智能指针样式封装确保释放。",
        )
        return Issue(
            category="memory",
            severity="warning",
            message=f"函数 `{cursor.spelling}` 中分配次数({allocs})多于释放次数({frees})，可能存在内存泄漏。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _collect_global_array(self, cursor) -> None:
        cindex = load_clang()
        if cursor.type.kind != cindex.TypeKind.CONSTANTARRAY or not cursor.spelling:
            return
        size = self._extract_array_size(cursor.type)
        if size is not None:
            self._global_array_sizes[cursor.spelling] = size

    def _extract_array_size(self, ctype) -> Optional[int]:
        try:
            size = ctype.get_array_size()
        except AttributeError:
            size = getattr(ctype, "element_count", None)
        if size is None:
            return None
        if size < 0:
            return None
        return int(size)

    def _check_array_bounds(self, cursor, array_sizes: Dict[str, int]) -> Optional[Issue]:
        children = list(cursor.get_children())
        if len(children) < 2:
            return None
        base, index_node = children[0], children[1]
        base_name = self._resolve_decl_name(base)
        if not base_name:
            return None
        size = array_sizes.get(base_name)
        if size is None:
            return None
        index_value = self._extract_constant_index(index_node)
        if index_value is None:
            return None
        if 0 <= index_value < size:
            return None
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title=f"确保索引位于 0 到 {size - 1} 之间",
            detail=f"当前访问的索引为 {index_value}，已超出数组 `{base_name}` 的大小 {size}。",
        )
        return Issue(
            category="memory",
            severity="error",
            message=f"数组 `{base_name}` 的访问索引 {index_value} 超出范围 (大小为 {size})。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _resolve_decl_name(self, cursor) -> Optional[str]:
        cindex = load_clang()
        if cursor.kind == cindex.CursorKind.DECL_REF_EXPR and cursor.spelling:
            referenced = cursor.referenced
            if referenced and referenced.spelling:
                return referenced.spelling
            return cursor.spelling
        return None

    def _extract_constant_index(self, cursor) -> Optional[int]:
        tokens = list(collect_tokens(cursor))
        if not tokens:
            return None
        text = "".join(tokens).replace(" ", "")
        try:
            # int(x, 0) 支持十六进制/八进制常量
            return int(text, 0)
        except ValueError:
            # 处理一元负号情况，如 tokens 形如 ['-', '1']
            if tokens[0] == "-" and len(tokens) == 2:
                try:
                    return -int(tokens[1], 0)
                except ValueError:
                    return None
        return None


__all__ = ["MemorySafetyChecker"]

