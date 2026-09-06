from pathlib import Path
import shutil

from easy_formula.models import RecognitionRecord
from easy_formula.pipeline import analyze_pdf, build_from_manifest, load_manifest
from easy_formula.results import save_results


def test_end_to_end_sample(tmp_path: Path):
    src = Path(__file__).resolve().parents[1] / "examples" / "sample.pdf"
    pdf = tmp_path / "demo.pdf"
    shutil.copy2(src, pdf)
    manifest_path = analyze_pdf(pdf, work_root=tmp_path / "work")
    manifest, candidates = load_manifest(manifest_path)

    records = []
    for c in candidates:
        if c.kind == "inline" and "β" in c.source_text:
            latex = r"\beta \in (0,1)"
        elif c.kind == "inline":
            latex = r"x_i"
        elif "∂" in c.source_text:
            latex = r"\frac{\partial U_i}{\partial x_i}=\alpha_i+\gamma x_i^2."
        else:
            latex = r"U_i(x)=\sum_{j=1}^{n}\beta_j x_{ij}."
        records.append(RecognitionRecord(c.candidate_id, True, latex, "high", True, ""))

    save_results(manifest["results_path"], pdf, records)
    out = build_from_manifest(manifest_path, compile_latex=False)
    assert out == pdf.with_suffix(".docx")
    assert out.exists()
