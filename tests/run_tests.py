"""运行内置测试并生成日志。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "tests" / "data"
LOG_DIR = PROJECT_ROOT / "tests" / "logs"
EXPECTED_FILE = PROJECT_ROOT / "tests" / "expected_results.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.analyzer.runner import AnalyzerRunner


def load_expected():
    if not EXPECTED_FILE.exists():
        return []
    with EXPECTED_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def run() -> Path:
    runner = AnalyzerRunner()
    sources = sorted(DATA_DIR.glob("*.c"))
    expected = load_expected()
    pending_expected = expected.copy()

    reports = []
    raw_outputs = []
    true_positive = 0

    for source in sources:
        report = runner.analyze(source)
        reports.append(report.to_dict())
        raw_text = report.format_text()
        raw_outputs.append(raw_text)

        matched_indices: set[int] = set()

        for issue in report.issues:
            match_index = _match_expected(issue, pending_expected)
            if match_index is not None:
                true_positive += 1
                matched_indices.add(match_index)

        for idx in sorted(matched_indices, reverse=True):
            pending_expected.pop(idx)

    false_negative = len(pending_expected)

    total_issues = sum(len(r["issues"]) for r in reports)
    false_positive = total_issues - true_positive

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"analysis-log-{timestamp}.json"

    log_data = {
        "generated_at": datetime.now().isoformat(),
        "sources": [str(src) for src in sources],
        "reports": reports,
        "raw_output": "\n\n".join(raw_outputs),
        "metrics": {
            "total_issues": total_issues,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
        "expected_reference": expected,
    }

    with log_path.open("w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    return log_path


def _match_expected(issue, expected):
    for index, rule in enumerate(expected):
        if issue.category == rule.get("category") and issue.line == rule.get("line"):
            return index
    return None


if __name__ == "__main__":  # pragma: no cover - 手动执行
    path = run()
    print(f"日志已生成: {path}")

