# Easy Formula V1

Easy Formula 用于从 PDF 学术文献中提取数学公式，转换为 LaTeX，并生成与原文献同名的 DOCX 文档。

## 设计目标

- 支持独立公式与行内公式；
- 支持单 PDF 与文件夹批量处理；
- Python 负责稳定的 PDF 解析、候选检测、裁剪和 DOCX 生成；
- 多模态 Agent 负责真正困难的公式视觉转写；
- 不绑定任何模型 API，也不在项目中保存 API Key；
- 低置信度结果不会被隐藏；
- DOCX 中除公式、LaTeX 与源数据外，所有说明文字均为简体中文。

## 安装

建议 Python 3.11+。

```bash
pip install -e .
```

如果运行环境无法联网获取构建依赖，但已经预装 setuptools，可使用：

```bash
pip install -e . --no-build-isolation
```

开发测试依赖：

```bash
pip install -e ".[dev]"
```

## Agent 推荐工作流

### 1. 分析

```bash
easy-formula analyze paper.pdf
```

终端会打印 `manifest.json` 和 `recognition_results.json` 的位置。

### 2. 视觉转写

按照 `SKILL.md`，查看 `crops/` 中的公式截图，填写 `recognition_results.json`。

### 3. 验证

```bash
easy-formula validate /path/to/manifest.json
```

### 4. 生成 DOCX

```bash
easy-formula build /path/to/manifest.json
```

最终得到：

```text
paper.pdf
paper.docx
```

## 批量处理

```bash
easy-formula analyze ./papers
```

递归：

```bash
easy-formula analyze ./papers --recursive
```

## 扫描型 PDF

分析结果中的 `scan_pages` 会列出缺少足够文本层的页面。Agent 应检查对应整页图片；如发现漏掉的公式，可补充：

```bash
easy-formula add-candidate manifest.json \
  --page 3 \
  --bbox 120,540,930,720 \
  --coords px
```

## 无视觉能力时的降级模式

```bash
easy-formula text-auto paper.pdf
```

该模式只利用 PDF 文本层进行保守转换，复杂公式准确率明显低于视觉 Agent，适合测试 Pipeline，不适合作为高精度最终结果。

## DOCX 结构

每个公式包括：

```text
公式 12
页码：7
公式类型：独立公式
原始公式：[截图]
LaTeX 代码：...
可直接使用的 LaTeX：...
识别置信度：高/中/低
```

低置信度或自动校验发现问题的公式会在文末再次汇总。

## 项目结构

```text
easy-formula-v1/
├── SKILL.md
├── README.md
├── pyproject.toml
├── easy_formula/
│   ├── cli.py
│   ├── pipeline.py
│   ├── pdf_inspector.py
│   ├── formula_detector.py
│   ├── formula_extractor.py
│   ├── text_latex.py
│   ├── verifier.py
│   ├── latex_renderer.py
│   └── docx_generator.py
├── prompts/
├── scripts/
├── tests/
└── examples/
```

## 测试

```bash
pytest -q
```
