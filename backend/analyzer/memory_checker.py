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
        self._leaky_functions: Set[str] = set()
        self._unsafe_pointer_returners: Set[str] = set()

    def run(self, context: AnalysisContext) -> Iterable[Issue]:
        cindex = load_clang()
        issues: List[Issue] = []

        self._global_uninitialized.clear()
        self._global_array_sizes.clear()
        self._leaky_functions.clear()
        self._unsafe_pointer_returners.clear()

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
        cindex = load_clang()

        issues: List[Issue] = []
        pointer_null: Set[str] = set()
        local_uninitialized: Set[str] = set()
        pointer_vars: Set[str] = set()
        freed_pointers: Set[str] = set()
        reported_uninitialized: Set[tuple[str, int, int]] = set()
        reported_null: Set[tuple[str, int, int]] = set()
        reported_uaf: Set[tuple[str, int, int]] = set()
        reported_double_free: Set[tuple[str, int, int]] = set()
        reported_leaky_calls: Set[tuple[str, int, int]] = set()

        array_sizes: Dict[str, int] = dict(self._global_array_sizes)
        allocation_calls = 0
        free_calls = 0
        returns_uninitialized_pointer = False

        def add_pointer_var(name: Optional[str]) -> None:
            if name:
                pointer_vars.add(name)

        def mark_initialized(name: Optional[str]) -> None:
            if not name:
                return
            local_uninitialized.discard(name)
            pointer_null.discard(name)
            freed_pointers.discard(name)

        def report_pointer_use(
            name: Optional[str],
            node,
            *,
            allow_freed: bool = False,
            guards: Optional[Set[str]] = None,
        ) -> None:
            if not name:
                return
            guards = guards or set()
            location_key = (name, node.location.line, node.location.column or 0)
            if name in freed_pointers and not allow_freed:
                if location_key not in reported_uaf:
                    reported_uaf.add(location_key)
                    issues.append(self._build_use_after_free_issue(node, name))
                return
            if name in pointer_null and name not in guards and name not in freed_pointers:
                if location_key not in reported_null:
                    reported_null.add(location_key)
                    issues.append(self._build_null_deref_issue(node, name))
                return
            if name in local_uninitialized or name in self._global_uninitialized:
                if location_key not in reported_uninitialized:
                    reported_uninitialized.add(location_key)
                    issues.append(self._build_uninitialized_pointer_issue(node, name))
                local_uninitialized.discard(name)

        # 收集形参与局部指针声明
        for param in cursor.get_arguments() or []:
            if param.type.kind == cindex.TypeKind.POINTER and param.spelling:
                add_pointer_var(param.spelling)

        for child in cursor.get_children():
            if child.kind == cindex.CursorKind.PARM_DECL:
                if child.type.kind == cindex.TypeKind.POINTER and child.spelling:
                    add_pointer_var(child.spelling)
                continue

            if child.kind == cindex.CursorKind.VAR_DECL and child.type.kind == cindex.TypeKind.POINTER:
                if child.spelling:
                    add_pointer_var(child.spelling)
                init_children = list(child.get_children())
                if not init_children:
                    if child.spelling:
                        local_uninitialized.add(child.spelling)
                else:
                    init_tokens = list(collect_tokens(child))
                    if child.spelling and ("NULL" in init_tokens or init_tokens[-1] == "0"):
                        pointer_null.add(child.spelling)
                    else:
                        mark_initialized(child.spelling)
            elif child.kind == cindex.CursorKind.VAR_DECL and child.type.kind == cindex.TypeKind.CONSTANTARRAY:
                size = self._extract_array_size(child.type)
                if child.spelling and size is not None:
                    array_sizes[child.spelling] = size

        def traverse(node, guards: frozenset[str]) -> None:
            nonlocal allocation_calls, free_calls, returns_uninitialized_pointer
            if node is cursor:
                for child in node.get_children():
                    traverse(child, guards)
                return

            if node.kind == cindex.CursorKind.FUNCTION_DECL:
                return

            tokens = list(collect_tokens(node))
            child_guard_context = guards

            if node.kind == cindex.CursorKind.VAR_DECL and getattr(node.type, "kind", None) == cindex.TypeKind.POINTER:
                parent = node.semantic_parent
                if parent and parent.kind not in {cindex.CursorKind.STRUCT_DECL, cindex.CursorKind.UNION_DECL}:
                    name = node.spelling
                    if name:
                        add_pointer_var(name)
                        init_children = list(node.get_children())
                        if not init_children:
                            local_uninitialized.add(name)
                        else:
                            init_tokens = [tok for tok in collect_tokens(node)]
                            if "NULL" in init_tokens or (init_tokens and init_tokens[-1] == "0"):
                                pointer_null.add(name)
                            else:
                                mark_initialized(name)

            if node.kind == cindex.CursorKind.BINARY_OPERATOR and tokens and "=" in tokens:
                target = self._resolve_assignment_target(node)
                rhs_cursor = self._resolve_assignment_rhs(node)
                raw_rhs_tokens = list(collect_tokens(rhs_cursor)) if rhs_cursor else tokens[tokens.index("=") + 1 :]
                rhs_tokens = [tok for tok in raw_rhs_tokens if tok not in {";", ",", "(", ")"}]
                callee = self._resolve_callee(rhs_cursor) if rhs_cursor else None

                if target and target in pointer_vars:
                    if callee in {"malloc", "calloc", "realloc"}:
                        mark_initialized(target)
                    elif callee and callee in self._unsafe_pointer_returners:
                        local_uninitialized.add(target)
                    elif rhs_tokens and rhs_tokens[0] == "&":
                        mark_initialized(target)
                    elif any(tok == "NULL" for tok in rhs_tokens) or (len(rhs_tokens) == 1 and rhs_tokens[0] in {"0", "nullptr"}):
                        pointer_null.add(target)
                        freed_pointers.discard(target)
                        local_uninitialized.discard(target)
                    else:
                        mark_initialized(target)

            if node.kind == cindex.CursorKind.CALL_EXPR:
                callee = self._resolve_callee(node)
                extra_safe: Set[str] = set()
                if callee in {"malloc", "calloc", "realloc"}:
                    allocation_calls += 1
                elif callee == "free":
                    free_calls += 1
                    for argument in node.get_arguments():
                        arg_name = self._resolve_decl_name(argument) or self._first_decl_ref_name(argument)
                        if not arg_name:
                            continue
                        location_key = (arg_name, argument.location.line, argument.location.column or 0)
                        if arg_name in freed_pointers and location_key not in reported_double_free:
                            reported_double_free.add(location_key)
                            issues.append(self._build_double_free_issue(argument, arg_name))
                        report_pointer_use(arg_name, argument, allow_freed=True, guards=set(guards))
                        freed_pointers.add(arg_name)
                        pointer_null.add(arg_name)
                        extra_safe.add(arg_name)
                else:
                    pass  # 避免在调用点重复报告泄漏/野指针返回

                for argument in node.get_arguments():
                    arg_name = self._resolve_decl_name(argument) or self._first_decl_ref_name(argument)
                    if arg_name:
                        report_pointer_use(arg_name, argument, allow_freed=(callee == "free"), guards=set(guards))

                if extra_safe:
                    child_guard_context = frozenset(set(guards).union(extra_safe))

            if node.kind == cindex.CursorKind.UNARY_OPERATOR and tokens and "*" in tokens:
                name = self._first_decl_ref_name(node)
                report_pointer_use(name, node, guards=set(guards))

            if node.kind == cindex.CursorKind.MEMBER_REF_EXPR and tokens and "->" in tokens:
                base_child = next(iter(node.get_children()), None)
                base_name = self._resolve_decl_name(base_child) if base_child else self._first_decl_ref_name(node)
                report_pointer_use(base_name, node, guards=set(guards))

            if node.kind == cindex.CursorKind.ARRAY_SUBSCRIPT_EXPR:
                children = list(node.get_children())
                base_name = self._resolve_decl_name(children[0]) if children else None
                report_pointer_use(base_name, node, guards=set(guards))
                array_issue = self._check_array_bounds(node, array_sizes)
                if array_issue:
                    issues.append(array_issue)

            if node.kind == cindex.CursorKind.RETURN_STMT:
                decl_names = self._collect_decl_ref_names(node)
                for name in decl_names:
                    if name in pointer_vars or name in self._global_uninitialized:
                        report_pointer_use(name, node, guards=set(guards))
                        if name in local_uninitialized or name in self._global_uninitialized:
                            returns_uninitialized_pointer = True

            if node.kind == cindex.CursorKind.IF_STMT:
                children = list(node.get_children())
                if not children:
                    return
                condition = children[0]
                traverse(condition, guards)
                guarded = self._extract_guarded_pointers(condition, pointer_vars)
                then_guards = frozenset(set(guards).union(guarded))
                if len(children) >= 2:
                    traverse(children[1], then_guards)
                if len(children) >= 3:
                    traverse(children[2], guards)
                for extra in children[3:]:
                    traverse(extra, guards)
                return

            for child in node.get_children():
                traverse(child, child_guard_context)

        traverse(cursor, frozenset())

        if allocation_calls > free_calls:
            issues.append(self._build_leak_issue(cursor, allocation_calls, free_calls))
            if cursor.spelling:
                self._leaky_functions.add(cursor.spelling)

        if returns_uninitialized_pointer and cursor.spelling:
            self._unsafe_pointer_returners.add(cursor.spelling)

        return issues

    def _walk(self, cursor):
        yield cursor
        cindex = load_clang()
        for child in iter_children(cursor):
            if child is cursor:
                continue
            if child.kind == cindex.CursorKind.FUNCTION_DECL:
                continue
            yield from self._walk(child)

    def _resolve_assignment_target(self, node) -> Optional[str]:
        children = list(node.get_children())
        if not children:
            return None
        lhs = children[0]
        cindex = load_clang()
        if lhs.kind == cindex.CursorKind.DECL_REF_EXPR:
            return self._resolve_decl_name(lhs) or lhs.spelling
        return None

    def _resolve_assignment_rhs(self, node):
        children = list(node.get_children())
        if len(children) < 2:
            return None
        return children[1]

    def _resolve_callee(self, node) -> Optional[str]:
        if node is None:
            return None
        referenced = getattr(node, "referenced", None)
        if referenced and getattr(referenced, "spelling", None):
            return referenced.spelling
        name = getattr(node, "spelling", None) or getattr(node, "displayname", None)
        if not name:
            return None
        return name.split("(")[0]

    def _first_decl_ref_name(self, node) -> Optional[str]:
        cindex = load_clang()
        for child in node.get_children():
            if child.kind == cindex.CursorKind.DECL_REF_EXPR and child.spelling:
                return child.spelling
            result = self._first_decl_ref_name(child)
            if result:
                return result
        return None

    def _collect_decl_ref_names(self, node) -> Set[str]:
        cindex = load_clang()
        names: Set[str] = set()
        for child in node.get_children():
            if child.kind == cindex.CursorKind.DECL_REF_EXPR and child.spelling:
                names.add(child.spelling)
            names.update(self._collect_decl_ref_names(child))
        return names

    def _extract_guarded_pointers(self, condition, pointer_vars: Set[str]) -> Set[str]:
        if condition is None:
            return set()
        cindex = load_clang()

        if condition.kind in {
            cindex.CursorKind.PAREN_EXPR,
            cindex.CursorKind.UNEXPOSED_EXPR,
        }:
            children = list(condition.get_children())
            guards: Set[str] = set()
            for child in children:
                guards |= self._extract_guarded_pointers(child, pointer_vars)
            return guards

        if condition.kind == cindex.CursorKind.BINARY_OPERATOR:
            tokens = list(collect_tokens(condition))
            children = list(condition.get_children())
            if "&&" in tokens and len(children) >= 2:
                guards: Set[str] = set()
                guards |= self._extract_guarded_pointers(children[0], pointer_vars)
                guards |= self._extract_guarded_pointers(children[1], pointer_vars)
                return guards
            if "||" in tokens:
                return set()
            if "!" in tokens and tokens.count("!") == 1 and len(children) == 1:
                return set()
            if "!=" in tokens and len(children) >= 2:
                left = children[0]
                right = children[1]
                name = self._resolve_decl_name(left) or self._first_decl_ref_name(left)
                right_tokens = {tok for tok in collect_tokens(right)}
                if name and name in pointer_vars and right_tokens & {"NULL", "0", "nullptr"}:
                    return {name}
                name = self._resolve_decl_name(right) or self._first_decl_ref_name(right)
                left_tokens = {tok for tok in collect_tokens(left)}
                if name and name in pointer_vars and left_tokens & {"NULL", "0", "nullptr"}:
                    return {name}
            return set()

        if condition.kind == cindex.CursorKind.DECL_REF_EXPR:
            if condition.spelling in pointer_vars:
                return {condition.spelling}
            return set()

        if condition.kind == cindex.CursorKind.UNARY_OPERATOR:
            tokens = list(collect_tokens(condition))
            if tokens and tokens[0] == "!":
                return set()
            child = next(condition.get_children(), None)
            return self._extract_guarded_pointers(child, pointer_vars)

        guards: Set[str] = set()
        for child in condition.get_children():
            guards |= self._extract_guarded_pointers(child, pointer_vars)
        return guards

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

    def _build_use_after_free_issue(self, cursor, name: str) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title=f"避免对 `{name}` 在释放后继续解引用",
            detail="释放内存后应立即将指针置为 NULL 或重新指向有效区域。",
        )
        return Issue(
            category="memory",
            severity="error",
            message=f"指针 `{name}` 在调用 `free` 后仍被使用，可能触发 Use-After-Free。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _build_double_free_issue(self, cursor, name: str) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title="确保每块内存仅释放一次",
            detail="可在释放后将指针赋值为 NULL，避免重复释放。",
        )
        return Issue(
            category="memory",
            severity="error",
            message=f"指针 `{name}` 可能被重复释放 (double free)。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _build_leaky_call_issue(self, cursor, callee: str) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title="在调用后释放被分配的资源",
            detail=f"函数 `{callee}` 已被推断可能泄漏动态内存，调用后请确认资源释放。",
        )
        return Issue(
            category="memory",
            severity="warning",
            message=f"调用 `{callee}` 可能引入未释放的内存。",
            file=file_path,
            line=line,
            column=column,
            suggestion=suggestion,
        )

    def _build_unsafe_return_call_issue(self, cursor, callee: str) -> Issue:
        file_path, line, column = cursor_location(cursor)
        suggestion = Suggestion(
            title="校验返回的指针是否指向有效内存",
            detail=f"函数 `{callee}` 返回的指针可能未初始化或指向失效区域，使用前需验证。",
        )
        return Issue(
            category="memory",
            severity="error",
            message=f"函数 `{callee}` 可能返回野指针，直接使用存在风险。",
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

