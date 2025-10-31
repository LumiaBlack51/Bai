"""后端包初始化。

该包负责对 C 语言源码执行静态分析，模块化拆分为解析、检查与结果汇总。
"""

from .cli import main

__all__ = ["main"]

