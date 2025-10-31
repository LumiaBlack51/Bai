"""分析工具函数。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Optional


@lru_cache(maxsize=1)
def load_clang() -> "clang.cindex":  # type: ignore[name-defined]
    """加载 clang Python 绑定。"""

    try:
        import clang.cindex as cindex  # type: ignore
    except ImportError as exc:  # pragma: no cover - 依赖问题
        raise RuntimeError(
            "未找到 clang Python 绑定。请先安装 `pip install clang` 并确保 libclang 可用。"
        ) from exc

    lib_path = os.getenv("LIBCLANG_PATH")
    if lib_path:
        cindex.Config.set_library_file(lib_path)

    # 尝试创建 Index 以验证库是否可用
    try:
        _ = cindex.Index.create()
    except Exception as exc:  # pragma: no cover - 依赖问题
        raise RuntimeError(
            "无法加载 libclang。请设置环境变量 LIBCLANG_PATH 指向 libclang 动态库。"
        ) from exc

    return cindex


def iter_children(cursor: "clang.cindex.Cursor") -> Iterator["clang.cindex.Cursor"]:  # type: ignore[name-defined]
    for child in cursor.get_children():
        yield child


def cursor_location(cursor: "clang.cindex.Cursor") -> tuple[Path, int, Optional[int]]:  # type: ignore[name-defined]
    location = cursor.extent.start
    return Path(location.file.name if location.file else "<unknown>"), location.line, location.column


def find_includes(translation_unit: "clang.cindex.TranslationUnit") -> set[str]:  # type: ignore[name-defined]
    includes: set[str] = set()
    for inc in translation_unit.get_includes():
        includes.add(Path(inc.include.name).name)
    return includes


def collect_tokens(cursor: "clang.cindex.Cursor") -> Iterator[str]:  # type: ignore[name-defined]
    for token in cursor.get_tokens():
        yield token.spelling


def safe_literal(token_sequence: Iterable[str]) -> Optional[str]:
    tokens = list(token_sequence)
    if not tokens:
        return None
    text = "".join(tokens)
    return text


__all__ = [
    "collect_tokens",
    "cursor_location",
    "find_includes",
    "iter_children",
    "load_clang",
    "safe_literal",
]

