# C 语言缺陷检测器

本项目依据 `requirements.md` 实现了一个原型级 C 语言静态缺陷检测器，支持命令行分析、报告生成与测试日志统计。

## 功能特性
- **内存安全**：识别未初始化指针使用、空指针解引用、动态内存泄漏等问题。
- **变量使用**：检测变量在赋值前被引用的风险。
- **标准库助手**：提示缺失的头文件、校验 `printf`/`scanf` 格式化参数数量。
- **数值与控制流**：识别除零、死循环与不可达代码。
- **日志统计**：`tests/run_tests.py` 输出原始报告与错报/漏报统计。

## 安装依赖
```bash
pip install -r requirements.txt
```

如无法自动找到 `libclang`，请设置环境变量 `LIBCLANG_PATH` 指向相应的动态库文件。

## 快速开始
```bash
python -m backend.cli tests/data/test_comprehensive_examples.c --json
```

## 运行测试并生成日志
```bash
python tests/run_tests.py
```

日志将保存在 `tests/logs/` 目录，内容包含：
- `raw_output`：逐文件检测的原始文本结果；
- `metrics`：真阳性、错报、漏报统计；
- `expected_reference`：用于比对的预期样例。

## VSCode 插件使用
- 进入 `frontend/vscode-extension/` 并执行 `npm install`（如需打包可使用 `npx vsce package`）。
- 在 VSCode 中使用 “运行扩展” 或安装打包好的 VSIX，即可启用 `C Bug Detector` 侧边栏。
- 快捷键 `Ctrl+Alt+D`（macOS `Cmd+Alt+D`）或编辑器标题栏按钮可对当前文件运行检测。
- 检测结果会同时出现在 *Problems* 面板与 `C Bug Detector` 视图，支持点击跳转、查看建议。
- 已生成 VSIX 包 `frontend/vscode-extension/c-bug-detector-0.1.0.vsix`，可直接在 VSCode 中通过 “扩展”→“从 VSIX 安装...” 导入。

## GitHub 提交指引
1. 在 GitHub 创建新的空仓库（例如 `c-bug-detector`）。
2. 在本地初始化仓库：
   ```bash
   git init
   git add .
   git commit -m "feat: initial static analyzer prototype"
   git remote add origin <你的仓库地址>
   git push -u origin main
   ```

如需在 VSCode 中开发插件，可在 `frontend/vscode-extension/` 目录继续扩展。

