from __future__ import annotations

import hashlib
from pathlib import Path

from .annotator import annotate_pages
from .docx_generator import generate_docx
from .formula_detector import detect_candidates
from .formula_extractor import extract_candidate_crops
from .input_resolver import resolve_jobs
from .io_utils import ensure_dir, read_json, write_json
from .models import FormulaCandidate, RecognitionRecord
from .pdf_inspector import inspect_pdf, render_page
from .results import create_results_template, load_results, save_results, validate_results
from .text_latex import unicode_math_to_latex
from .verifier import verify_all

SCHEMA_VERSION = 1


def _workspace_for(pdf_path: Path, work_root: str | Path | None = None) -> Path:
    if work_root is None:
        base = pdf_path.parent / ".easy_formula"
    else:
        base = Path(work_root).expanduser().resolve()
    digest = hashlib.sha1(str(pdf_path.resolve()).encode("utf-8")).hexdigest()[:8]
    return base / f"{pdf_path.stem}-{digest}"


def analyze_pdf(
    pdf_path: str | Path,
    output_docx: str | Path | None = None,
    work_root: str | Path | None = None,
    include_inline: bool = True,
    page_dpi: int = 150,
    crop_dpi: int = 240,
) -> Path:
    pdf_path = Path(pdf_path).expanduser().resolve()
    output_docx = Path(output_docx).expanduser().resolve() if output_docx else pdf_path.with_suffix(".docx")
    workspace = _workspace_for(pdf_path, work_root)
    page_dir = ensure_dir(workspace / "pages")
    annotated_dir = ensure_dir(workspace / "annotated_pages")
    crops_dir = ensure_dir(workspace / "crops")

    pages, metadata = inspect_pdf(pdf_path)
    candidates = detect_candidates(pages, include_inline=include_inline)

    pages_to_render = sorted({c.page_number for c in candidates} | {p.page_number for p in pages if p.visual_scan_required})
    page_images: dict[int, Path] = {}
    for page_number in pages_to_render:
        out = page_dir / f"page_{page_number:04d}.png"
        render_page(pdf_path, page_number, out, dpi=page_dpi)
        page_images[page_number] = out

    extract_candidate_crops(pdf_path, candidates, crops_dir, dpi=crop_dpi)
    annotated = annotate_pages(pages, candidates, page_images, annotated_dir)
    for c in candidates:
        if c.page_number in annotated:
            c.page_image_path = str(annotated[c.page_number].resolve())

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source_pdf": str(pdf_path),
        "output_docx": str(output_docx),
        "workspace": str(workspace.resolve()),
        "page_count": metadata["page_count"],
        "metadata": metadata.get("metadata", {}),
        "scan_pages": [p.page_number for p in pages if p.visual_scan_required],
        "page_sizes": {str(p.page_number): [p.width, p.height] for p in pages},
        "page_images": {str(k): str(v.resolve()) for k, v in page_images.items()},
        "annotated_pages": {str(k): str(v.resolve()) for k, v in annotated.items()},
        "candidates": [c.to_dict() for c in candidates],
        "results_path": str((workspace / "recognition_results.json").resolve()),
        "notes": [
            "scan_pages 中的页面缺少足够文本层，需要调用 Agent 视觉能力检查页面是否存在漏检公式。",
            "候选检测允许误报；最终是否为公式由 recognition_results.json 中的 is_formula 决定。",
        ],
    }
    manifest_path = write_json(workspace / "manifest.json", manifest)
    create_results_template(pdf_path, candidates, workspace / "recognition_results.json")
    return manifest_path


def load_manifest(manifest_path: str | Path) -> tuple[dict, list[FormulaCandidate]]:
    data = read_json(manifest_path)
    candidates = [FormulaCandidate.from_dict(item) for item in data.get("candidates", [])]
    return data, candidates


def fill_text_fallback(manifest_path: str | Path) -> Path:
    manifest, candidates = load_manifest(manifest_path)
    records: list[RecognitionRecord] = []
    for c in candidates:
        latex = unicode_math_to_latex(c.source_text)
        # Text-layer fallback is intentionally conservative.
        confidence = "medium" if c.detector_score >= 0.75 and latex else "low"
        records.append(
            RecognitionRecord(
                candidate_id=c.candidate_id,
                is_formula=bool(latex),
                latex=latex,
                confidence=confidence,  # type: ignore[arg-type]
                visual_verified=False,
                notes="由 PDF 文本层自动转换，尚未进行视觉核对。",
            )
        )
    return save_results(manifest["results_path"], manifest["source_pdf"], records)


def build_from_manifest(
    manifest_path: str | Path,
    results_path: str | Path | None = None,
    overwrite: bool = False,
    allow_incomplete: bool = False,
    compile_latex: bool = True,
) -> Path:
    manifest, candidates = load_manifest(manifest_path)
    results_path = Path(results_path or manifest["results_path"])
    records = load_results(results_path)
    errors = validate_results(candidates, records, allow_incomplete=allow_incomplete)
    if errors and not allow_incomplete:
        raise ValueError("识别结果尚未准备完成：\n- " + "\n- ".join(errors))

    if allow_incomplete:
        by_id = {r.candidate_id: r for r in records}
        normalized: list[RecognitionRecord] = []
        for c in candidates:
            r = by_id.get(c.candidate_id)
            if r is None or r.is_formula is None:
                normalized.append(RecognitionRecord(candidate_id=c.candidate_id, is_formula=False))
            else:
                normalized.append(r)
        records = normalized

    verification = verify_all(candidates, records, compile_latex=compile_latex)
    output = Path(manifest["output_docx"])
    if output.exists() and not overwrite:
        raise FileExistsError(f"输出文件已存在：{output}。如需覆盖，请使用 --overwrite。")
    generate_docx(manifest["source_pdf"], output, candidates, records, verification)

    report = {
        "source_pdf": manifest["source_pdf"],
        "output_docx": str(output.resolve()),
        "confirmed_formulas": sum(r.is_formula is True for r in records),
        "rejected_candidates": sum(r.is_formula is False for r in records),
        "low_confidence": sum(v.final_confidence == "low" for v in verification.values()),
        "verification": {
            cid: {
                "final_confidence": vr.final_confidence,
                "syntax_ok": vr.syntax_ok,
                "issues": vr.issues,
            }
            for cid, vr in verification.items()
        },
    }
    write_json(Path(manifest["workspace"]) / "build_report.json", report)
    return output


def analyze_input(
    input_path: str | Path,
    recursive: bool = False,
    output_dir: str | Path | None = None,
    work_root: str | Path | None = None,
    include_inline: bool = True,
) -> list[Path]:
    manifests: list[Path] = []
    for job in resolve_jobs(input_path, recursive=recursive, output_dir=output_dir):
        manifests.append(analyze_pdf(job.source_pdf, job.output_docx, work_root=work_root, include_inline=include_inline))
    return manifests


def add_visual_candidate(
    manifest_path: str | Path,
    page_number: int,
    bbox: tuple[float, float, float, float],
    coords: str = "pdf",
    crop_dpi: int = 240,
) -> str:
    """Add a visually identified formula candidate, mainly for scanned pages.

    bbox uses PDF points by default. With coords='px', bbox is interpreted in
    the rendered page image coordinate system stored in the manifest.
    """
    from PIL import Image
    from .formula_extractor import crop_visual_candidate

    manifest, candidates = load_manifest(manifest_path)
    if page_number < 1 or page_number > int(manifest["page_count"]):
        raise ValueError("页码超出范围。")

    bbox_pdf = tuple(float(v) for v in bbox)
    if coords == "px":
        page_image = manifest.get("page_images", {}).get(str(page_number))
        if not page_image:
            raise ValueError("该页没有已渲染页面图像，无法使用像素坐标。")
        with Image.open(page_image) as img:
            iw, ih = img.size
        pw, ph = manifest["page_sizes"][str(page_number)]
        sx, sy = pw / iw, ph / ih
        x0, y0, x1, y1 = bbox_pdf
        bbox_pdf = (x0 * sx, y0 * sy, x1 * sx, y1 * sy)
    elif coords != "pdf":
        raise ValueError("coords 仅支持 pdf 或 px。")

    next_num = 1
    if candidates:
        next_num = max(int(c.candidate_id[1:]) for c in candidates if c.candidate_id.startswith("F")) + 1
    cid = f"F{next_num:04d}"
    workspace = Path(manifest["workspace"])
    crop_path = workspace / "crops" / f"{cid}.png"
    crop_visual_candidate(manifest["source_pdf"], page_number, bbox_pdf, crop_path, dpi=crop_dpi)
    candidate = FormulaCandidate(
        candidate_id=cid,
        page_number=page_number,
        kind="visual",
        bbox_pdf=bbox_pdf,
        detector_score=1.0,
        detector_reason=["由 Agent 页面视觉检查补充"],
        crop_path=str(crop_path.resolve()),
        page_image_path=manifest.get("page_images", {}).get(str(page_number)),
    )
    candidates.append(candidate)
    candidates.sort(key=lambda c: (c.page_number, c.bbox_pdf[1], c.bbox_pdf[0]))
    manifest["candidates"] = [c.to_dict() for c in candidates]
    write_json(manifest_path, manifest)

    # Preserve existing results and append a placeholder for the new candidate.
    results_path = Path(manifest["results_path"])
    existing = load_results(results_path) if results_path.exists() else []
    if not any(r.candidate_id == cid for r in existing):
        existing.append(RecognitionRecord(candidate_id=cid))
        save_results(results_path, manifest["source_pdf"], existing)
    return cid
