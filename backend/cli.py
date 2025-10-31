"""命令行接口。

该模块提供一个简单的 CLI，支持对单个或多个 C 源文件执行分析，
并以人类可读或 JSON 格式输出报告。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List

from .analyzer.runner import AnalyzerRunner
from .config import AnalyzerConfig, DEFAULT_CONFIG


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbug-detector",
        description="静态检测 C 语言源码中的常见缺陷",
    )
    parser.add_argument("sources", nargs="+", help="待分析的 C 源码文件")
    parser.add_argument(
        "--compile-arg",
        action="append",
        default=None,
        help="向 clang 传递额外的编译参数，可重复",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出完整报告",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="将结果写入指定文件 (默认输出到标准输出)",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="遇到首个错误时立即停止后续检查",
    )
    return parser


def _normalize_sources(sources: Iterable[str]) -> List[Path]:
    result: List[Path] = []
    for src in sources:
        path = Path(src).resolve()
        if not path.exists():
            raise FileNotFoundError(f"未找到源码文件: {path}")
        result.append(path)
    return result


def main(argv: List[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    compile_args = args.compile_arg if args.compile_arg is not None else DEFAULT_CONFIG.compile_args
    config = AnalyzerConfig(
        compile_args=list(compile_args),
        enable_suggestions=True,
        stop_on_error=args.stop_on_error,
    )

    runner = AnalyzerRunner(config=config)
    sources = _normalize_sources(args.sources)

    reports = []
    for src in sources:
        report = runner.analyze(src)
        reports.append(report)
        if config.stop_on_error and report.has_errors:
            break

    output = args.output.open("w", encoding="utf-8") if args.output else sys.stdout
    try:
        if args.json:
            json.dump([r.to_dict() for r in reports], output, ensure_ascii=False, indent=2)
        else:
            for report in reports:
                output.write(report.format_text())
                output.write("\n")
    finally:
        if args.output:
            output.close()

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 入口
    raise SystemExit(main())

