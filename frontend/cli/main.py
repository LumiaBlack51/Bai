"""CLI 前端绑定。"""

from __future__ import annotations

from backend.cli import main as backend_main


def run(argv=None) -> int:
    """供外部脚本调用的入口。"""

    return backend_main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())

