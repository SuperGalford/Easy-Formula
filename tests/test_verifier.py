from easy_formula.models import FormulaCandidate, RecognitionRecord
from easy_formula.verifier import verify_record


def candidate():
    return FormulaCandidate(
        candidate_id="F0001",
        page_number=1,
        kind="display",
        bbox_pdf=(10, 10, 100, 30),
        detector_score=0.9,
    )


def test_verified_high_stays_high_without_compile():
    r = RecognitionRecord(
        candidate_id="F0001",
        is_formula=True,
        latex=r"x_i=\alpha",
        confidence="high",
        visual_verified=True,
    )
    v = verify_record(candidate(), r, compile_latex=False)
    assert v.final_confidence == "high"
    assert v.syntax_ok


def test_unbalanced_downshifts():
    r = RecognitionRecord(
        candidate_id="F0001",
        is_formula=True,
        latex=r"\frac{x}{y",
        confidence="high",
        visual_verified=True,
    )
    v = verify_record(candidate(), r, compile_latex=False)
    assert v.final_confidence == "medium"
    assert not v.syntax_ok
