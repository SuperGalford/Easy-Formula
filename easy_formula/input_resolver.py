from __future__ import annotations

from pathlib import Path

from .models import ProcessingJob


class InputResolutionError(ValueError):
    pass


def resolve_jobs(input_path: str | Path, recursive: bool = False, output_dir: str | Path | None = None) -> list[ProcessingJob]:
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise InputResolutionError(f"输入路径不存在：{path}")

    if path.is_file():
        if path.suffix.lower() != ".pdf":
            raise InputResolutionError("单文件模式仅支持 PDF 文件。")
        return [_make_job(path, output_dir)]

    if not path.is_dir():
        raise InputResolutionError("输入必须是 PDF 文件或文件夹。")

    iterator = path.rglob("*") if recursive else path.iterdir()
    pdf_files = sorted(p for p in iterator if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdf_files:
        raise InputResolutionError("该文件夹中没有找到 PDF 文件。")
    return [_make_job(pdf, output_dir) for pdf in pdf_files]


def _make_job(pdf_path: Path, output_dir: str | Path | None) -> ProcessingJob:
    if output_dir is None:
        out = pdf_path.with_suffix(".docx")
    else:
        out_dir = Path(output_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{pdf_path.stem}.docx"
    return ProcessingJob(source_pdf=pdf_path, output_docx=out)
