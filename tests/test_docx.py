from pathlib import Path

from PIL import Image
from docx import Document

from easy_formula.docx_generator import generate_docx
from easy_formula.models import FormulaCandidate, RecognitionRecord, VerificationResult


def test_docx_uses_chinese_labels(tmp_path: Path):
    crop = tmp_path / "formula.png"
    Image.new("RGB", (600, 120), "white").save(crop)
    c = FormulaCandidate(
        candidate_id="F0001",
        page_number=7,
        kind="display",
        bbox_pdf=(0, 0, 100, 20),
        equation_number="12",
        crop_path=str(crop),
    )
    r = RecognitionRecord(
        candidate_id="F0001",
        is_formula=True,
        latex=r"U_i=\sum_{j=1}^{n}\beta_jx_{ij}",
        confidence="high",
        visual_verified=True,
    )
    v = VerificationResult("F0001", "high", True, [])
    out = tmp_path / "paper.docx"
    generate_docx(tmp_path / "paper.pdf", out, [c], [r], {"F0001": v})
    assert out.exists()

    doc = Document(out)
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "公式提取结果" in text
    assert "页码：7" in text
    assert "公式类型：独立公式" in text
    assert "识别置信度：高" in text
    assert "Raw LaTeX" not in text
    assert "Confidence" not in text
