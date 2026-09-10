# Easy Formula

Easy Formula 是一个供 Codex Agent 使用的 Skill。它能从 PDF 学术文献中定位数学公式，转写为 LaTeX，进行视觉核对，并生成中文 DOCX 结果文档。

## 使用前准备

用户只需在运行 Agent 的设备上安装 Python 3.11 或更高版本，并确保 Agent 可以读取待处理的 PDF、在输出目录中创建文件。

无需手动安装 PyMuPDF、python-docx、Pillow 或其他运行依赖。首次调用本 Skill 时，Agent 会检查并自动安装缺少的依赖；如 Python 缺失、版本不足，或当前环境不允许安装依赖，Agent 会说明需要处理的具体问题。

不需要配置 API Key、公式 OCR 服务或命令行工具。

## 安装 Skill

把本仓库链接交给 Agent，并说：

```text
请从 https://github.com/SuperGalford/easy-formula 安装 easy-formula Skill。
```

安装后，Agent 可在处理 PDF 公式时调用该 Skill。

## 如何触发

上传或提供 PDF 文件后，直接向 Agent 发出自然语言请求。

提取全部公式并生成 Word 文档：

```text
请使用 easy-formula 提取这篇论文中的全部公式，转成 LaTeX，并生成 Word 文档。
```

只提取独立公式：

```text
请使用 easy-formula 提取这篇论文中的独立公式，不需要行内公式，并生成 Word 文档。
```

提取全部公式（包括行内公式）：

```text
请使用 easy-formula 完整提取这篇论文中的所有公式，包括行内公式；请转成 LaTeX 并生成 Word 文档。
```

只处理指定页码：

```text
请使用 easy-formula 提取该 PDF 第 5 至 10 页中的公式，并生成 Word 文档。
```

## Agent 会完成的工作

Agent 将：

1. 解析 PDF 并定位候选公式；
2. 检查公式截图，排除网址、页码、参考文献和普通正文等误报；
3. 将确认公式转写为 LaTeX；
4. 二次核对符号、上下标、分式、矩阵和括号；
5. 标注识别置信度；
6. 生成与原 PDF 同名的中文 DOCX 文档。

每条公式在 DOCX 中包含页码、类型、原始截图、LaTeX 代码、可直接使用的 LaTeX 和识别置信度。低置信度或自动校验发现问题的公式会在文末“需要人工核对的公式”部分汇总。

## 适用范围

- 单篇 PDF；
- 文件夹中的多篇 PDF；
- 独立公式与行内公式；
- 扫描型 PDF 页面；
- 中文 DOCX 公式提取报告。
