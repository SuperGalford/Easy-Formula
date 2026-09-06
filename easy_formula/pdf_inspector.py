from __future__ import annotations

from pathlib import Path

import fitz

from .models import PageInfo, TextChar, TextLine, TextSpan


def inspect_pdf(pdf_path: str | Path, scan_text_threshold: int = 30) -> tuple[list[PageInfo], dict]:
    pdf_path = Path(pdf_path)
    doc = fitz.open(pdf_path)
    pages: list[PageInfo] = []

    for page_index, page in enumerate(doc):
        page_dict = page.get_text("rawdict")
        lines: list[TextLine] = []
        text_parts: list[str] = []

        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans: list[TextSpan] = []
                line_text_parts: list[str] = []
                line_bbox = tuple(float(v) for v in line.get("bbox", (0, 0, 0, 0)))
                for span in line.get("spans", []):
                    chars: list[TextChar] = []
                    char_text: list[str] = []
                    for ch in span.get("chars", []):
                        c = str(ch.get("c", ""))
                        bbox = tuple(float(v) for v in ch.get("bbox", (0, 0, 0, 0)))
                        chars.append(TextChar(char=c, bbox=bbox))
                        char_text.append(c)
                    text = "".join(char_text)
                    if not text:
                        continue
                    bbox = tuple(float(v) for v in span.get("bbox", (0, 0, 0, 0)))
                    spans.append(
                        TextSpan(
                            text=text,
                            bbox=bbox,
                            font=str(span.get("font", "")),
                            size=float(span.get("size", 0.0)),
                            flags=int(span.get("flags", 0)),
                            chars=chars,
                        )
                    )
                    line_text_parts.append(text)
                line_text = "".join(line_text_parts).strip()
                if line_text:
                    lines.append(TextLine(text=line_text, bbox=line_bbox, spans=spans))
                    text_parts.append(line_text)

        text = "\n".join(text_parts)
        char_count = sum(1 for c in text if not c.isspace())
        pages.append(
            PageInfo(
                page_number=page_index + 1,
                width=float(page.rect.width),
                height=float(page.rect.height),
                text=text,
                lines=lines,
                text_char_count=char_count,
                visual_scan_required=char_count < scan_text_threshold,
            )
        )

    metadata = {
        "page_count": len(doc),
        "metadata": doc.metadata or {},
        "is_encrypted": bool(doc.is_encrypted),
        "source_pdf": str(pdf_path.resolve()),
    }
    doc.close()
    return pages, metadata


def render_page(pdf_path: str | Path, page_number: int, output_path: str | Path, dpi: int = 150) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    pix.save(str(output_path))
    doc.close()
    return output_path
