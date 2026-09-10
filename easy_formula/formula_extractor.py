from __future__ import annotations

from pathlib import Path

import fitz

from .models import FormulaCandidate


def extract_candidate_crops(
    pdf_path: str | Path,
    candidates: list[FormulaCandidate],
    crops_dir: str | Path,
    dpi: int = 240,
) -> list[FormulaCandidate]:
    pdf_path = Path(pdf_path)
    crops_dir = Path(crops_dir)
    crops_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    scale = dpi / 72.0

    for cand in candidates:
        page = doc[cand.page_number - 1]
        rect = fitz.Rect(*cand.bbox_pdf) & page.rect
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False)
        out = crops_dir / f"{cand.candidate_id}.png"
        pix.save(str(out))
        cand.crop_path = str(out.resolve())

    doc.close()
    return candidates


def crop_visual_candidate(
    pdf_path: str | Path,
    page_number: int,
    bbox_pdf: tuple[float, float, float, float],
    output_path: str | Path,
    dpi: int = 240,
) -> Path:
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    rect = fitz.Rect(*bbox_pdf) & page.rect
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_path))
    doc.close()
    return output_path
