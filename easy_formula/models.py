from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

FormulaKind = Literal["display", "inline", "visual"]
Confidence = Literal["high", "medium", "low"]


@dataclass
class TextChar:
    char: str
    bbox: tuple[float, float, float, float]


@dataclass
class TextSpan:
    text: str
    bbox: tuple[float, float, float, float]
    font: str
    size: float
    flags: int = 0
    chars: list[TextChar] = field(default_factory=list)


@dataclass
class TextLine:
    text: str
    bbox: tuple[float, float, float, float]
    spans: list[TextSpan] = field(default_factory=list)


@dataclass
class PageInfo:
    page_number: int
    width: float
    height: float
    text: str
    lines: list[TextLine]
    text_char_count: int
    visual_scan_required: bool = False


@dataclass
class FormulaCandidate:
    candidate_id: str
    page_number: int
    kind: FormulaKind
    bbox_pdf: tuple[float, float, float, float]
    source_text: str = ""
    equation_number: str | None = None
    detector_score: float = 0.0
    detector_reason: list[str] = field(default_factory=list)
    crop_path: str | None = None
    page_image_path: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["bbox_pdf"] = list(self.bbox_pdf)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "FormulaCandidate":
        data = dict(data)
        data["bbox_pdf"] = tuple(data["bbox_pdf"])
        return cls(**data)


@dataclass
class RecognitionRecord:
    candidate_id: str
    is_formula: bool | None = None
    latex: str = ""
    confidence: Confidence = "low"
    visual_verified: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RecognitionRecord":
        return cls(**data)


@dataclass
class VerificationResult:
    candidate_id: str
    final_confidence: Confidence
    syntax_ok: bool
    issues: list[str] = field(default_factory=list)
    rendered_preview: str | None = None


@dataclass(frozen=True)
class ProcessingJob:
    source_pdf: Path
    output_docx: Path
