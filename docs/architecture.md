# 架构概览

## 模块划分
- `backend/`：Python 静态分析后端，基于 `clang` 解析源码并输出检测报告。
  - `analyzer/`：具体检查器与运行器，包含内存安全、变量使用、标准库助手、数值与控制流检查模块。
  - `cli.py`：命令行入口，通过参数驱动分析流程。
- `frontend/cli/`：前端命令行封装，供后续扩展 VSCode 插件时复用。
- `tests/`：测试数据与日志脚本，`run_tests.py` 可执行批量分析并统计错报/漏报。
- `docs/`：项目文档。

## 数据流
1. CLI 接收源文件路径与额外编译参数。
2. `AnalyzerRunner` 使用 `ASTParser` 调用 libclang 构建 AST。
3. 每个 `Checker` 接收 `AnalysisContext`，独立产生 `Issue`。
4. `Report` 聚合所有 `Issue`，支持文本与 JSON 输出。
5. 测试脚本收集报告，结合 `expected_results.json` 计算指标，并生成日志。

## 依赖
- Python 3.10+
- `clang` Python 绑定，需可访问 `libclang` 动态库。

## 后续扩展建议
- 在 `analyzer` 内新增 `use_after_free`、`array_bounds` 等更精细检查。
- 在 `frontend` 目录下扩展 `vscode-extension`，与后端通过 JSON 通信。
- 引入单元测试框架（如 `pytest`）验证各个检查器。

