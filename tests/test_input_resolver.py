from pathlib import Path

import pytest

from easy_formula.input_resolver import InputResolutionError, resolve_jobs


def test_single_pdf(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    jobs = resolve_jobs(pdf)
    assert len(jobs) == 1
    assert jobs[0].output_docx.name == "paper.docx"


def test_directory_batch(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4\n")
    (tmp_path / "b.PDF").write_bytes(b"%PDF-1.4\n")
    (tmp_path / "ignore.txt").write_text("x", encoding="utf-8")
    jobs = resolve_jobs(tmp_path)
    assert [j.source_pdf.name for j in jobs] == ["a.pdf", "b.PDF"]


def test_reject_non_pdf(tmp_path: Path):
    p = tmp_path / "x.txt"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(InputResolutionError):
        resolve_jobs(p)
