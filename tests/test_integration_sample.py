from pathlib import Path

from easy_formula.pipeline import analyze_pdf, load_manifest


def test_analyze_shipped_sample(tmp_path: Path):
    sample = Path(__file__).resolve().parents[1] / "examples" / "sample.pdf"
    manifest_path = analyze_pdf(sample, output_docx=tmp_path / "sample.docx", work_root=tmp_path / "work")
    manifest, candidates = load_manifest(manifest_path)

    display = [c for c in candidates if c.kind == "display"]
    inline = [c for c in candidates if c.kind == "inline"]
    assert len(display) >= 2
    assert len(inline) >= 1
    assert manifest["scan_pages"] == []
    assert all(c.crop_path and Path(c.crop_path).exists() for c in candidates)
