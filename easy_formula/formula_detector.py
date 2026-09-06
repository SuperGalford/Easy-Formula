from __future__ import annotations

import re
from dataclasses import replace

from .models import FormulaCandidate, PageInfo, TextChar, TextLine, TextSpan

GREEK_RE = re.compile(r"[Α-Ωα-ωϑϕϵϖς]")
STRONG_MATH_RE = re.compile(r"[=≠≤≥≈≃≅≡∈∉∋⊂⊆⊃⊇∑∏∫∬∭√∂∇∞±∓×÷∝∼→←↔⇒⇔⊥∥∧∨⊕⊗]")
ASCII_MATH_RE = re.compile(r"[+\-*/^<>]=?|:=|\b(?:sin|cos|tan|log|ln|exp|max|min|argmax|argmin)\b", re.I)
EQNO_RE = re.compile(r"^\s*(?:\(|\[)\s*(\d+(?:\.\d+)*[a-zA-Z]?)\s*(?:\)|\])\s*$")
TRAILING_EQNO_RE = re.compile(r"(?:\(|\[)\s*(\d+(?:\.\d+)*[a-zA-Z]?)\s*(?:\)|\])\s*$")
ONLY_NUMBER_RE = re.compile(r"^\s*[\[(]?\d+(?:\.\d+)*[\])]?\s*[.,]?\s*$")
REFERENCEISH_RE = re.compile(r"\b(?:19|20)\d{2}\b")
SINGLE_VAR_RE = re.compile(r"^[A-Za-zΑ-Ωα-ω](?:['′″])?$|^[A-Za-zΑ-Ωα-ω][₀-₉]+$")

MATH_FONT_HINTS = (
    "math", "symbol", "cmmi", "cmsy", "cmex", "msam", "msbm", "stix",
    "euler", "cambria math", "latinmodernmath", "mt extra", "mathjax",
)
ITALIC_FONT_HINTS = ("italic", "oblique", "slanted")
INLINE_NEUTRAL = set("0123456789 +-*/^_=<>|()[]{}.,;:'′″")


def _font_math_score(font: str) -> float:
    name = font.lower().replace("-", " ")
    return 1.0 if any(h in name for h in MATH_FONT_HINTS) else 0.0


def _font_italic(font: str) -> bool:
    name = font.lower().replace("-", " ")
    return any(h in name for h in ITALIC_FONT_HINTS)


def _text_math_score(text: str) -> tuple[float, list[str]]:
    t = text.strip()
    if not t or ONLY_NUMBER_RE.match(t):
        return 0.0, []
    score = 0.0
    reasons: list[str] = []
    if STRONG_MATH_RE.search(t):
        score += 0.42
        reasons.append("包含强数学运算符")
    if GREEK_RE.search(t):
        score += 0.22
        reasons.append("包含希腊字母")
    if ASCII_MATH_RE.search(t):
        score += 0.18
        reasons.append("包含数学运算结构")
    if TRAILING_EQNO_RE.search(t):
        score += 0.12
        reasons.append("包含公式编号")
    digits = sum(c.isdigit() for c in t)
    ascii_ops = sum(c in "+-*/^_=<>|{}[]()" for c in t)
    alpha = sum(c.isalpha() for c in t)
    nonspace = max(1, sum(not c.isspace() for c in t))
    if (digits + ascii_ops) / nonspace > 0.18:
        score += 0.12
        reasons.append("数字与运算符密度较高")
    if alpha > 0 and ascii_ops > 0 and len(t) < 100:
        score += 0.08
    if REFERENCEISH_RE.search(t) and not STRONG_MATH_RE.search(t):
        score -= 0.22
    if len(t) > 180:
        score -= 0.25
    return max(0.0, min(score, 1.0)), reasons


def _line_math_font_ratio(line: TextLine) -> float:
    math_chars = 0
    total_chars = 0
    for span in line.spans:
        n = sum(not c.isspace() for c in span.text)
        total_chars += n
        if _font_math_score(span.font):
            math_chars += n
    return math_chars / max(1, total_chars)


def _line_geometry_score(line: TextLine, page: PageInfo) -> tuple[float, list[str]]:
    x0, _, x1, _ = line.bbox
    width = max(1.0, x1 - x0)
    page_width = max(1.0, page.width)
    center = (x0 + x1) / 2
    centeredness = 1 - min(1.0, abs(center - page_width / 2) / (page_width / 2))
    score = 0.0
    reasons: list[str] = []
    if width < page_width * 0.78:
        score += 0.08
        reasons.append("行宽较短")
    if centeredness > 0.72:
        score += 0.12
        reasons.append("位置接近页面中心")
    return score, reasons


def _display_seed(line: TextLine, page: PageInfo) -> tuple[bool, float, list[str]]:
    if ONLY_NUMBER_RE.match(line.text):
        return False, 0.0, []
    text_score, reasons = _text_math_score(line.text)
    geom_score, geom_reasons = _line_geometry_score(line, page)
    ratio = _line_math_font_ratio(line)
    words = re.findall(r"[A-Za-z]{2,}", line.text)
    font_score = min(0.32, ratio * 0.38)
    total = min(1.0, text_score + geom_score + font_score)
    if ratio >= 0.25:
        reasons.append("包含数学字体")
    reasons += geom_reasons

    # Long prose containing one inline equation must not become a display formula.
    prose_heavy = len(words) >= 6 and ratio < 0.35
    evidence = text_score >= 0.18 or ratio >= 0.45
    return (evidence and total >= 0.42 and not prose_heavy), total, reasons


def _bbox_union(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(b[0] for b in boxes), min(b[1] for b in boxes),
        max(b[2] for b in boxes), max(b[3] for b in boxes),
    )


def _axis_gap(a0: float, a1: float, b0: float, b1: float) -> float:
    if a1 < b0:
        return b0 - a1
    if b1 < a0:
        return a0 - b1
    return 0.0


def _axis_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _lines_connect(a: TextLine, b: TextLine) -> bool:
    ax0, ay0, ax1, ay1 = a.bbox
    bx0, by0, bx1, by1 = b.bbox
    hgap = _axis_gap(ax0, ax1, bx0, bx1)
    vgap = _axis_gap(ay0, ay1, by0, by1)
    hoverlap = _axis_overlap(ax0, ax1, bx0, bx1)
    voverlap = _axis_overlap(ay0, ay1, by0, by1)
    min_h = max(1.0, min(ay1 - ay0, by1 - by0))
    min_w = max(1.0, min(ax1 - ax0, bx1 - bx0))

    if voverlap / min_h > 0.35 and hgap <= 34:
        return True
    if hoverlap / min_w > 0.20 and vgap <= 16:
        return True
    if hgap <= 12 and vgap <= 12:
        return True
    return False


def _cluster_seed_lines(seed_items: list[tuple[TextLine, float, list[str]]]) -> list[list[tuple[TextLine, float, list[str]]]]:
    remaining = list(seed_items)
    clusters: list[list[tuple[TextLine, float, list[str]]]] = []
    while remaining:
        cluster = [remaining.pop(0)]
        changed = True
        while changed:
            changed = False
            for item in remaining[:]:
                if any(_lines_connect(item[0], existing[0]) for existing in cluster):
                    cluster.append(item)
                    remaining.remove(item)
                    changed = True
        clusters.append(cluster)
    return clusters


def _vertical_related(line_bbox, cluster_bbox) -> bool:
    _, y0, _, y1 = line_bbox
    _, cy0, _, cy1 = cluster_bbox
    gap = _axis_gap(y0, y1, cy0, cy1)
    overlap = _axis_overlap(y0, y1, cy0, cy1)
    min_h = max(1.0, min(y1 - y0, cy1 - cy0))
    return overlap / min_h > 0.25 or gap <= 5


def _pad_bbox(bbox: tuple[float, float, float, float], page: PageInfo, xpad: float, ypad: float) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = bbox
    return (
        max(0.0, x0 - xpad), max(0.0, y0 - ypad),
        min(page.width, x1 + xpad), min(page.height, y1 + ypad),
    )


def _char_core_math(ch: str, font: str) -> bool:
    if not ch or ch.isspace():
        return False
    if _font_math_score(font):
        return True
    if GREEK_RE.match(ch) or STRONG_MATH_RE.match(ch):
        return True
    if ch in "=+−-*/^<>±×÷∂∇∞":
        return True
    if _font_italic(font) and ch.isalpha():
        return True
    return False


def _inline_runs(line: TextLine) -> list[tuple[str, tuple[float, float, float, float], float, list[str]]]:
    chars: list[tuple[str, tuple[float, float, float, float], str]] = []
    for span in line.spans:
        if span.chars:
            chars.extend((c.char, c.bbox, span.font) for c in span.chars)
        else:
            # Fallback when character boxes are unavailable.
            for c in span.text:
                chars.append((c, span.bbox, span.font))

    runs: list[tuple[str, tuple[float, float, float, float], float, list[str]]] = []
    i = 0
    while i < len(chars):
        ch, bbox, font = chars[i]
        if not _char_core_math(ch, font):
            i += 1
            continue
        start = i
        end = i + 1
        core_count = 1
        # Extend left through nearby neutral mathematical punctuation/digits.
        while start > 0:
            pch, pb, _ = chars[start - 1]
            cb = chars[start][1]
            gap = _axis_gap(pb[0], pb[2], cb[0], cb[2])
            if pch in INLINE_NEUTRAL and gap <= 2.5:
                start -= 1
            else:
                break
        # Extend right through core chars and neutral chars. Stop at prose letters.
        while end < len(chars):
            nch, nb, nf = chars[end]
            prevb = chars[end - 1][1]
            gap = _axis_gap(prevb[0], prevb[2], nb[0], nb[2])
            if gap > 4.0:
                break
            if _char_core_math(nch, nf):
                core_count += 1
                end += 1
                continue
            if nch in INLINE_NEUTRAL:
                end += 1
                continue
            break

        selected = chars[start:end]
        text = "".join(x[0] for x in selected).strip()
        # Trim neutral punctuation/spaces from ends while retaining brackets/digits.
        text = text.strip(" ,;:")
        if text and core_count > 0 and not ONLY_NUMBER_RE.match(text):
            boxes = [x[1] for x in selected if not x[0].isspace()]
            if boxes:
                score, reasons = _text_math_score(text)
                if any(_font_math_score(x[2]) for x in selected):
                    score = min(1.0, score + 0.35)
                    reasons.append("数学字体")
                if score >= 0.35 or SINGLE_VAR_RE.match(text):
                    runs.append((text, _bbox_union(boxes), max(score, 0.48 if SINGLE_VAR_RE.match(text) else score), reasons))
        i = max(end, i + 1)
    return runs


def _intersection(a, b) -> float:
    x0 = max(a[0], b[0]); y0 = max(a[1], b[1]); x1 = min(a[2], b[2]); y1 = min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _area(b) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _overlap_ratio_bbox(a, b) -> float:
    return _intersection(a, b) / max(1.0, min(_area(a), _area(b)))


def detect_candidates(pages: list[PageInfo], include_inline: bool = True) -> list[FormulaCandidate]:
    candidates: list[FormulaCandidate] = []

    for page in pages:
        if page.visual_scan_required:
            continue

        seed_items: list[tuple[TextLine, float, list[str]]] = []
        for line in page.lines:
            is_seed, score, reasons = _display_seed(line, page)
            if is_seed:
                seed_items.append((line, score, reasons))

        display_boxes: list[tuple[float, float, float, float]] = []
        for cluster in _cluster_seed_lines(seed_items):
            cluster_lines = [item[0] for item in cluster]
            box = _bbox_union([line.bbox for line in cluster_lines])
            eqno: str | None = None
            # Attach a right-side equation number aligned with the equation cluster.
            for line in page.lines:
                m = EQNO_RE.match(line.text)
                if not m:
                    continue
                if line.bbox[0] > box[2] and _vertical_related(line.bbox, box):
                    eqno = m.group(1)
                    box = _bbox_union([box, line.bbox])
                    break

            texts = [line.text for line in sorted(cluster_lines, key=lambda x: (x.bbox[1], x.bbox[0]))]
            reasons = list(dict.fromkeys(r for _, _, rs in cluster for r in rs))
            score = max(item[1] for item in cluster)
            padded = _pad_bbox(box, page, xpad=5, ypad=3)
            display_boxes.append(padded)
            candidates.append(
                FormulaCandidate(
                    candidate_id="",
                    page_number=page.page_number,
                    kind="display",
                    bbox_pdf=padded,
                    source_text=" ".join(texts),
                    equation_number=eqno,
                    detector_score=round(score, 3),
                    detector_reason=reasons,
                )
            )

        if include_inline:
            for line in page.lines:
                if any(_overlap_ratio_bbox(line.bbox, dbox) > 0.55 for dbox in display_boxes):
                    continue
                for text, box, score, reasons in _inline_runs(line):
                    padded = _pad_bbox(box, page, xpad=2.5, ypad=2)
                    if any(_overlap_ratio_bbox(padded, dbox) > 0.50 for dbox in display_boxes):
                        continue
                    candidates.append(
                        FormulaCandidate(
                            candidate_id="",
                            page_number=page.page_number,
                            kind="inline",
                            bbox_pdf=padded,
                            source_text=text,
                            detector_score=round(min(score, 1.0), 3),
                            detector_reason=reasons,
                        )
                    )

    # De-duplicate strongly overlapping candidates of the same kind.
    deduped: list[FormulaCandidate] = []
    for cand in sorted(candidates, key=lambda c: (-c.detector_score, c.page_number, c.bbox_pdf[1], c.bbox_pdf[0])):
        duplicate = any(
            cand.page_number == other.page_number
            and cand.kind == other.kind
            and _overlap_ratio_bbox(cand.bbox_pdf, other.bbox_pdf) > 0.86
            for other in deduped
        )
        if not duplicate:
            deduped.append(cand)

    deduped.sort(key=lambda c: (c.page_number, c.bbox_pdf[1], c.bbox_pdf[0], 0 if c.kind == "display" else 1))
    return [replace(c, candidate_id=f"F{i:04d}") for i, c in enumerate(deduped, start=1)]
