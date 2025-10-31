# C Bug Detector VSCode 插件

该插件通过调用项目后端的 Python 分析器，为当前打开的 C/C++ 源文件提供静态缺陷检测，并将结果同步到 VSCode 的 *Problems* 面板与侧边栏视图。

## 功能特性

- **一键检测**：在编辑器标题栏按钮、命令面板或快捷键 `Ctrl+Alt+D`（macOS 为 `Cmd+Alt+D`）触发分析。
- **问题高亮**：自动填写 Diagnostics，问题与建议展示在 *Problems* 面板中。
- **侧边报告面板**：`C Bug Detector` 视图列出各文件的所有问题，点击即可跳转至对应行列。
- **修改建议**：若后端提供建议，侧边视图和诊断信息中均会展示标题与详细说明。
- **自定义配置**：`cBugDetector.pythonPath` 指定 Python 解释器，`cBugDetector.extraArgs` 可附加编译参数。

## 使用说明

1. 在 VSCode 中打开本项目目录，确保后端 Python 环境可执行 `python -m backend.cli`。
2. 进入 `frontend/vscode-extension`，执行 `npm install`（如需打包可运行 `npx vsce package`）。
3. 通过 VSCode 选择 “运行和调试” → “运行扩展”，或使用 `vsce` 打包后安装。
4. 在 C 语言源文件中点击编辑器工具栏按钮、执行命令 `C Bug Detector: 运行当前文件检测`，或使用快捷键。

## 目录结构

- `extension.js`：插件主入口，负责命令注册、进程调用、诊断同步与树视图更新。
- `resources/icon.svg`：活动栏图标。
- `package.json`：插件清单与贡献点声明。

## 运行需求

- VSCode 版本 1.75.0 及以上。
- 系统可访问的 Python 3 环境（可通过配置项自定义路径）。
- 已安装 clang Python 绑定及 `requirements.txt` 中的依赖。

## 常见问题

- **命令执行失败**：检查 `C Bug Detector` 输出面板，确认 Python 路径与后端依赖是否正确。必要时设置 `LIBCLANG_PATH`。
- **无问题输出**：若后端返回为空，侧边栏显示“没有检测到问题”。如需强制刷新，可再次执行检测命令。

欢迎后续在此基础上扩展更多 VSCode 功能，如问题修复自动化或代码片段补全等。

