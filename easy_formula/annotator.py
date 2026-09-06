from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

from .models import FormulaCandidate, PageInfo


def annotate_pages(
    pages: list[PageInfo],
    candidates: list[FormulaCandidate],
    page_images: dict[int, Path],
    output_dir: str | Path,
) -> dict[int, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    by_page: dict[int, list[FormulaCandidate]] = defaultdict(list)
    for c in candidates:
        by_page[c.page_number].append(c)

    page_map = {p.page_number: p for p in pages}
    outputs: dict[int, Path] = {}
    for page_number, image_path in page_images.items():
        page = page_map[page_number]
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        sx = img.width / page.width
        sy = img.height / page.height
        for cand in by_page.get(page_number, []):
            x0, y0, x1, y1 = cand.bbox_pdf
            rect = [int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)]
            draw.rectangle(rect, outline="black", width=max(2, img.width // 700))
            label = cand.candidate_id
            tx = rect[0]
            ty = max(0, rect[1] - 16)
            # White backing keeps the ASCII candidate id legible on dense papers.
            box = [tx, ty, tx + 50, ty + 15]
            draw.rectangle(box, fill="white", outline="black")
            draw.text((tx + 2, ty + 1), label, fill="black")
        out = output_dir / f"page_{page_number:04d}.png"
        img.save(out)
        outputs[page_number] = out
    return outputs
