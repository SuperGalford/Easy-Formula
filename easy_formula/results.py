from __future__ import annotations

from pathlib import Path

from .io_utils import read_json, write_json
from .models import FormulaCandidate, RecognitionRecord

SCHEMA_VERSION = 1


class ResultsValidationError(ValueError):
    pass


def create_results_template(source_pdf: str | Path, candidates: list[FormulaCandidate], output_path: str | Path) -> Path:
    data = {
        "schema_version": SCHEMA_VERSION,
        "source_pdf": str(Path(source_pdf).resolve()),
        "instructions": "请逐个查看 crop_path 对应的公式图片；确认是否为公式，并填写 LaTeX、置信度和视觉核对状态。",
        "results": [RecognitionRecord(candidate_id=c.candidate_id).to_dict() for c in candidates],
    }
    return write_json(output_path, data)


def load_results(path: str | Path) -> list[RecognitionRecord]:
    data = read_json(path)
    return [RecognitionRecord.from_dict(item) for item in data.get("results", [])]


def save_results(path: str | Path, source_pdf: str | Path, records: list[RecognitionRecord]) -> Path:
    return write_json(path, {
        "schema_version": SCHEMA_VERSION,
        "source_pdf": str(Path(source_pdf).resolve()),
        "results": [r.to_dict() for r in records],
    })


def validate_results(candidates: list[FormulaCandidate], records: list[RecognitionRecord], allow_incomplete: bool = False) -> list[str]:
    candidate_ids = {c.candidate_id for c in candidates}
    by_id = {r.candidate_id: r for r in records}
    errors: list[str] = []

    unknown = set(by_id) - candidate_ids
    if unknown:
        errors.append("识别结果包含未知候选编号：" + ", ".join(sorted(unknown)))

    for cid in sorted(candidate_ids):
        r = by_id.get(cid)
        if r is None:
            errors.append(f"缺少候选 {cid} 的识别结果。")
            continue
        if r.is_formula is None and not allow_incomplete:
            errors.append(f"候选 {cid} 尚未确认是否为公式。")
        if r.is_formula is True and not r.latex.strip():
            errors.append(f"候选 {cid} 已确认为公式，但 LaTeX 为空。")
        if r.confidence not in {"high", "medium", "low"}:
            errors.append(f"候选 {cid} 的置信度无效：{r.confidence}")
    return errors
