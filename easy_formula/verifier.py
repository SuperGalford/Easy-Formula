from __future__ import annotations

from .latex_renderer import latex_compile_check
from .models import FormulaCandidate, RecognitionRecord, VerificationResult

PAIRS = {"{": "}", "[": "]", "(": ")"}
CLOSERS = set(PAIRS.values())


def _balanced(latex: str) -> bool:
    stack: list[str] = []
    escaped = False
    for c in latex:
        if escaped:
            escaped = False
            continue
        if c == "\\":
            escaped = True
            continue
        if c in PAIRS:
            stack.append(PAIRS[c])
        elif c in CLOSERS:
            if not stack or stack.pop() != c:
                return False
    return not stack


def _downshift(confidence: str) -> str:
    return {"high": "medium", "medium": "low", "low": "low"}.get(confidence, "low")


def verify_record(candidate: FormulaCandidate, record: RecognitionRecord, compile_latex: bool = True) -> VerificationResult:
    if record.is_formula is not True:
        return VerificationResult(candidate_id=candidate.candidate_id, final_confidence="low", syntax_ok=True, issues=[])

    issues: list[str] = []
    syntax_ok = True
    latex = record.latex.strip()
    confidence = record.confidence

    if not latex:
        syntax_ok = False
        issues.append("LaTeX 为空。")
        confidence = "low"
    if latex and not _balanced(latex):
        syntax_ok = False
        issues.append("括号或花括号不平衡。")
        confidence = _downshift(confidence)
    if not record.visual_verified:
        issues.append("尚未完成视觉二次核对。")
        confidence = _downshift(confidence)
    if candidate.detector_score < 0.55 and confidence == "high":
        issues.append("候选检测置信度较低，已将最终置信度降为中。")
        confidence = "medium"

    if latex and compile_latex:
        compiled, message = latex_compile_check(latex)
        if not compiled:
            syntax_ok = False
            issues.append("LaTeX 编译失败。")
            issues.append(message)
            confidence = "low"

    return VerificationResult(
        candidate_id=candidate.candidate_id,
        final_confidence=confidence,  # type: ignore[arg-type]
        syntax_ok=syntax_ok,
        issues=issues,
    )


def verify_all(candidates: list[FormulaCandidate], records: list[RecognitionRecord], compile_latex: bool = True) -> dict[str, VerificationResult]:
    candidate_map = {c.candidate_id: c for c in candidates}
    output: dict[str, VerificationResult] = {}
    for record in records:
        candidate = candidate_map.get(record.candidate_id)
        if candidate is None:
            continue
        output[record.candidate_id] = verify_record(candidate, record, compile_latex=compile_latex)
    return output
