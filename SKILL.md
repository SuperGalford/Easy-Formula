---
name: easy-formula
description: 从 PDF 学术文献中定位独立公式与行内公式，使用多模态视觉能力转写为 LaTeX，进行二次核对和语法校验，并生成与 PDF 同名的中文 DOCX 公式文档。适用于单篇 PDF 与文件夹批量处理。
---

# Easy Formula V1

> 如果环境中尚未安装 `easy-formula` 命令，可在项目根目录将本文中的 `easy-formula ...` 替换为 `python -m easy_formula ...`。

## 目标

当用户要求从 PDF 文献提取公式、转成 LaTeX、生成 Word/DOCX 时，使用本 Skill。

核心流程：

```text
PDF
→ 页面与文本层解析
→ 公式候选检测
→ 公式区域截图
→ Agent 视觉转写 LaTeX
→ Agent 二次视觉核对
→ LaTeX 结构/编译检查
→ 中文 DOCX
```

## 固定输出规则

1. 输出 DOCX 默认与原 PDF 同目录、同名，仅扩展名改为 `.docx`。
2. DOCX 中除以下内容外，所有可见说明文字必须使用简体中文：
   - 数学公式本身；
   - LaTeX 代码；
   - 原始文件名等不可翻译的源数据。
3. 每个确认公式至少包含：
   - 公式序号；
   - 页码；
   - 公式类型；
   - 原始公式截图；
   - LaTeX 代码；
   - 可直接使用的 LaTeX；
   - 识别置信度。
4. 低置信度公式必须保留，并在文末“需要人工核对的公式”中再次列出。
5. Detector 的候选允许误报；最终必须由 Agent 设置 `is_formula` 来确认或剔除。
6. 不要把普通正文、参考文献年份、页码、单独的章节编号误当成公式。

## 第一步：分析 PDF

单文件：

```bash
easy-formula analyze "paper.pdf"
```

文件夹：

```bash
easy-formula analyze "./papers"
```

需要递归：

```bash
easy-formula analyze "./papers" --recursive
```

命令会生成一个工作区，其中核心文件为：

```text
manifest.json
recognition_results.json
crops/
annotated_pages/
pages/
```

读取 `manifest.json`。不要跳过这一步。

## 第二步：处理扫描页

查看 `manifest.json` 的 `scan_pages`。

若为空，继续下一步。

若不为空：

1. 查看对应 `page_images` 中的整页图片。
2. 检查是否存在 Detector 因缺少文本层而漏掉的公式。
3. 若存在，用公式区域的像素坐标补充候选：

```bash
easy-formula add-candidate manifest.json --page 3 --bbox 120,540,930,720 --coords px
```

4. 重新读取 `manifest.json` 与 `recognition_results.json`。

不要因为页面缺少文本层就假定该页没有公式。

## 第三步：逐个识别公式

对于 `manifest.json` 中每个 candidate：

1. 优先查看 `crop_path` 对应截图。
2. 必要时查看 `page_image_path` 对应的带标记整页图，理解上下文。
3. 判断它是否真的属于数学公式：
   - 是：`is_formula = true`
   - 否：`is_formula = false`
4. 若为公式，只转写截图中真正的数学表达式。
5. 原文右侧的公式编号如 `(1)`、`(12a)` 不写进 LaTeX；编号由 DOCX 的“原文公式编号”字段单独保存。
6. 不解释公式含义，不翻译变量，不补充原文不存在的符号。

### LaTeX 转写要求

必须特别检查：

- 上标与下标；
- 多层上下标；
- 分式；
- 根号；
- 希腊字母；
- 求和、乘积、积分；
- 偏导、梯度；
- 括号层级；
- 条件符号；
- 绝对值与范数；
- 帽子、横线、波浪号；
- 粗体、向量；
- 黑板粗体与花体；
- 矩阵、cases、aligned 等多行结构。

不要为了“让公式更漂亮”而重写原公式。

## 第四步：二次视觉核对

第一次完成 LaTeX 后，必须再次对照公式截图，从左到右或按数学结构逐项检查。

核对至少包括：

- 符号是否一致；
- 数字是否一致；
- 上下标归属是否一致；
- 括号是否成对；
- 分子分母是否颠倒；
- 求和/积分上下限是否正确；
- 希腊字母是否混淆；
- 字体语义是否遗漏，如 `\mathbf`、`\mathbb`、`\mathcal`。

完成核对后：

```json
{
  "candidate_id": "F0001",
  "is_formula": true,
  "latex": "U_i=\\sum_{j=1}^{n}\\beta_j x_{ij}",
  "confidence": "high",
  "visual_verified": true,
  "notes": ""
}
```

置信度只能使用：

```text
high
medium
low
```

如果截图模糊、符号无法确定，不要猜成高置信度。填写最佳转写，并设为 `low`，`notes` 用中文简短说明不确定位置。

若 candidate 为误报：

```json
{
  "candidate_id": "F0002",
  "is_formula": false,
  "latex": "",
  "confidence": "low",
  "visual_verified": true,
  "notes": "该候选为正文编号，不是数学公式。"
}
```

将所有结果写回工作区的 `recognition_results.json`。

## 第五步：验证识别结果

运行：

```bash
easy-formula validate manifest.json
```

如果报告尚未完成，修正 `recognition_results.json`，不要直接跳到 build。

## 第六步：生成 DOCX

```bash
easy-formula build manifest.json
```

如果目标 DOCX 已存在，先判断是否应该覆盖。需要覆盖时：

```bash
easy-formula build manifest.json --overwrite
```

默认会做 LaTeX 括号结构检查，并在环境存在 `pdflatex` 时进行编译检查。

## 第七步：最终 QA

生成 DOCX 后：

1. 确认文件与源 PDF 同名。
2. 确认公式按 PDF 中的顺序排列。
3. 确认原始公式截图可见且未被裁切。
4. 确认 LaTeX 代码没有被 Word 自动改写。
5. 确认除公式、LaTeX、源数据外的说明文字全部为简体中文。
6. 若环境具备 DOCX 渲染能力，渲染为页面图像并检查是否有图片溢出、文字裁切或分页异常。

## 批量模式

对文件夹运行 `analyze` 后，每篇 PDF 会有独立工作区。逐篇完成视觉识别与 `build`，不要把不同论文的结果混在同一个 `recognition_results.json` 中。

## 纯 CLI 备用模式

如果当前环境完全没有多模态视觉能力，可使用：

```bash
easy-formula text-auto "paper.pdf"
```

该模式只根据 PDF 文本层做保守的 Unicode 数学符号 → LaTeX 转换，不能可靠恢复复杂分式、矩阵或排版结构，因此必须视为降级模式，不应冒充视觉识别结果。

## V1 范围

V1 已支持：

- 单 PDF；
- 文件夹批量；
- 独立公式候选；
- 行内公式候选；
- 扫描页标记与 Agent 手动补充候选；
- 原公式截图；
- Agent 多模态 LaTeX 转写协议；
- 误报剔除；
- 高/中/低置信度；
- LaTeX 结构检查；
- 可选 pdflatex 编译检查；
- 中文 DOCX；
- 待人工核对区域。

V1 不承诺完全自动、无人监督地恢复所有扫描型 PDF 中的公式坐标；扫描页依赖调用本 Skill 的视觉 Agent 进行页面检查与候选补充。
