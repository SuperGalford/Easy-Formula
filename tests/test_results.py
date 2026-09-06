from easy_formula.models import FormulaCandidate, RecognitionRecord
from easy_formula.results import validate_results


def test_results_require_confirmation():
    c = FormulaCandidate("F0001", 1, "inline", (0, 0, 10, 10))
    errors = validate_results([c], [RecognitionRecord("F0001")])
    assert errors


def test_false_positive_is_valid():
    c = FormulaCandidate("F0001", 1, "inline", (0, 0, 10, 10))
    errors = validate_results([c], [RecognitionRecord("F0001", is_formula=False, visual_verified=True)])
    assert errors == []
