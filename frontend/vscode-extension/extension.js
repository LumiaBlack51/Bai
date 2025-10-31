const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');

/**
 * @typedef {{
 *  category: string,
 *  severity: string,
 *  message: string,
 *  file: string,
 *  line: number,
 *  column?: number,
 *  suggestion?: { title?: string, detail?: string }
 * }} AnalyzerIssue
 */

/**
 * @typedef {{ source: string, issues: AnalyzerIssue[], summary?: Record<string, number> }} AnalyzerReport
 */

/**
 * @param {AnalyzerIssue} issue
 */
function issueToDiagnostic(issue) {
  const severityMap = {
    error: vscode.DiagnosticSeverity.Error,
    warning: vscode.DiagnosticSeverity.Warning,
    info: vscode.DiagnosticSeverity.Information
  };

  const severity = severityMap[issue.severity] || vscode.DiagnosticSeverity.Warning;
  const line = Math.max(0, (issue.line || 1) - 1);
  const column = Math.max(0, (issue.column || 1) - 1);
  const start = new vscode.Position(line, column);
  const diagnostic = new vscode.Diagnostic(new vscode.Range(start, start), buildMessage(issue), severity);
  diagnostic.source = 'C Bug Detector';
  diagnostic.code = issue.category;
  return diagnostic;
}

/**
 * @param {AnalyzerIssue} issue
 */
function buildMessage(issue) {
  const parts = [issue.message];
  if (issue.suggestion) {
    if (issue.suggestion.title) {
      parts.push(`建议: ${issue.suggestion.title}`);
    }
    if (issue.suggestion.detail) {
      parts.push(issue.suggestion.detail);
    }
  }
  return parts.join('\n');
}

class FileNode extends vscode.TreeItem {
  /**
   * @param {AnalyzerReport} report
   * @param {string | undefined} workspacePath
   */
  constructor(report, workspacePath) {
    const label = path.basename(report.source);
    super(label, vscode.TreeItemCollapsibleState.Expanded);
    this.report = report;
    this.contextValue = 'cBugDetector.file';
    this.description = workspacePath ? path.relative(workspacePath, report.source) : report.source;
    this.iconPath = new vscode.ThemeIcon('file-code');
  }
}

class IssueNode extends vscode.TreeItem {
  /**
   * @param {AnalyzerIssue} issue
   */
  constructor(issue) {
    super(issue.message, vscode.TreeItemCollapsibleState.None);
    this.issue = issue;
    this.contextValue = 'cBugDetector.issue';
    this.command = {
      command: 'cBugDetector.openIssue',
      title: '打开问题位置',
      arguments: [issue]
    };
    this.tooltip = buildMessage(issue);
    this.iconPath = new vscode.ThemeIcon(getSeverityIcon(issue.severity));
    this.description = `第 ${issue.line} 行 · ${issue.category}`;
  }
}

function getSeverityIcon(severity) {
  switch (severity) {
    case 'error':
      return 'error';
    case 'info':
      return 'info';
    default:
      return 'warning';
  }
}

class ReportTreeDataProvider {
  constructor() {
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
    /** @type {AnalyzerReport[]} */
    this._reports = [];
    this._workspacePath = undefined;
  }

  /**
   * @param {AnalyzerReport[]} reports
   * @param {string | undefined} workspacePath
   */
  refresh(reports, workspacePath) {
    this._reports = reports;
    this._workspacePath = workspacePath;
    this._onDidChangeTreeData.fire(undefined);
  }

  clear() {
    this.refresh([], this._workspacePath);
  }

  /**
   * @param {FileNode | IssueNode | undefined} element
   */
  getChildren(element) {
    if (!element) {
      return this._reports.map(report => new FileNode(report, this._workspacePath));
    }
    if (element instanceof FileNode) {
      return element.report.issues.map(issue => new IssueNode(issue));
    }
    return [];
  }

  /**
   * @param {FileNode | IssueNode} element
   */
  getTreeItem(element) {
    return element;
  }
}

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  const diagnostics = vscode.languages.createDiagnosticCollection('cBugDetector');
  const output = vscode.window.createOutputChannel('C Bug Detector');
  const treeDataProvider = new ReportTreeDataProvider();
  const treeView = vscode.window.createTreeView('cBugDetector.reportView', {
    treeDataProvider
  });

  async function runAnalysis(targetUri) {
    const activeEditor = vscode.window.activeTextEditor;
    const uri = targetUri instanceof vscode.Uri
      ? targetUri
      : activeEditor?.document.uri;

    if (!uri) {
      vscode.window.showWarningMessage('请先打开一个 C 语言源文件。');
      return;
    }

    const workspaceFolder = vscode.workspace.getWorkspaceFolder(uri) || vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      vscode.window.showErrorMessage('请先在 VSCode 中打开包含后端代码的工作区。');
      return;
    }

    const document = activeEditor?.document;
    if (document && document.isDirty && document.uri.toString() === uri.toString()) {
      await document.save();
    }

    const config = vscode.workspace.getConfiguration('cBugDetector');
    const pythonPath = config.get('pythonPath') || 'python';
    const extraArgs = Array.isArray(config.get('extraArgs')) ? config.get('extraArgs') : [];

    const args = ['-m', 'backend.cli', uri.fsPath, '--json', ...extraArgs];
    const cwd = workspaceFolder.uri.fsPath;

    output.appendLine(`[${new Date().toISOString()}] 运行: ${pythonPath} ${args.join(' ')}`);

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'C Bug Detector 正在分析...'
      },
      () => new Promise((resolve, reject) => {
        const child = cp.spawn(pythonPath, args, {
          cwd,
          env: {
            ...process.env,
            PYTHONIOENCODING: 'utf-8'
          }
        });

        let stdout = '';
        let stderr = '';

        child.stdout.on('data', (data) => {
          stdout += data.toString();
        });

        child.stderr.on('data', (data) => {
          const text = data.toString();
          stderr += text;
          output.appendLine(text);
        });

        child.on('error', (error) => {
          output.appendLine(`执行失败: ${error.message}`);
          reject(new Error(`无法启动 Python 进程: ${error.message}`));
        });

        child.on('close', (code) => {
          if (typeof code === 'number' && code !== 0) {
            output.appendLine(`分析器以状态码 ${code} 退出。`);
            if (stdout.trim()) {
              output.appendLine(stdout.trim());
            }
            reject(new Error(stderr.trim() || `分析器以状态码 ${code} 退出`));
            return;
          }

          try {
            const reports = parseReports(stdout);
            applyDiagnostics(reports, diagnostics);
            treeDataProvider.refresh(reports, cwd);
            updateTreeMessage(treeView, reports);
            const totalIssues = reports.reduce((sum, report) => sum + report.issues.length, 0);
            vscode.window.showInformationMessage(`C Bug Detector 分析完成，发现 ${totalIssues} 个问题。`);
            resolve(undefined);
          } catch (error) {
            treeDataProvider.clear();
            diagnostics.clear();
            reject(error);
          }
        });
      })
    ).catch((error) => {
      vscode.window.showErrorMessage(error.message || 'C Bug Detector 分析失败。');
    });
  }

  /**
   * @param {AnalyzerIssue} issue
   */
  async function openIssue(issue) {
    try {
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(issue.file));
      const editor = await vscode.window.showTextDocument(doc, { preview: false });
      const line = Math.max(0, (issue.line || 1) - 1);
      const column = Math.max(0, (issue.column || 1) - 1);
      const position = new vscode.Position(line, column);
      editor.selection = new vscode.Selection(position, position);
      editor.revealRange(new vscode.Range(position, position), vscode.TextEditorRevealType.InCenter);
    } catch (error) {
      vscode.window.showErrorMessage(`无法打开文件: ${error}`);
    }
  }

  const runCommand = vscode.commands.registerCommand('cBugDetector.runAnalysis', runAnalysis);
  const openCommand = vscode.commands.registerCommand('cBugDetector.openIssue', openIssue);

  context.subscriptions.push(runCommand, openCommand, diagnostics, output, treeView);
}

/**
 * @param {string} stdout
 * @returns {AnalyzerReport[]}
 */
function parseReports(stdout) {
  if (!stdout.trim()) {
    return [];
  }

  let parsed;
  try {
    parsed = JSON.parse(stdout);
  } catch (error) {
    throw new Error('无法解析后端输出，请检查后台命令是否成功执行。');
  }

  if (!Array.isArray(parsed)) {
    throw new Error('后端返回格式不正确。');
  }

  return parsed;
}

/**
 * @param {AnalyzerReport[]} reports
 * @param {vscode.DiagnosticCollection} diagnostics
 */
function applyDiagnostics(reports, diagnostics) {
  diagnostics.clear();
  for (const report of reports) {
    const uri = vscode.Uri.file(report.source);
    const diags = report.issues.map(issueToDiagnostic);
    diagnostics.set(uri, diags);
  }
}

/**
 * @param {vscode.TreeView<FileNode | IssueNode>} treeView
 * @param {AnalyzerReport[]} reports
 */
function updateTreeMessage(treeView, reports) {
  if (!treeView) {
    return;
  }
  if (!reports.length) {
    treeView.message = '没有检测到问题。';
    return;
  }

  const summaryTexts = reports.map((report) => {
    const summary = report.summary || {};
    const summaryParts = Object.keys(summary)
      .map((key) => `${key}:${summary[key]}`)
      .join(' ');
    return `${path.basename(report.source)} (${summaryParts || '无'})`;
  });
  treeView.message = summaryTexts.join(' | ');
}

function deactivate() {
  // 空实现即可
}

module.exports = {
  activate,
  deactivate
};

