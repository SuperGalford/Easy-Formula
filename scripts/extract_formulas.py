#!/usr/bin/env python3
"""
Formula Extraction Script - Extracts mathematical formulas from academic literature
and converts them to LaTeX code, saved to a Word document.

Supports:
- DOCX: Parses OMML equations and converts to LaTeX
- PDF: Extracts formula regions using layout analysis + Mathpix API
"""

import argparse
import base64
import os
import re
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

# ── OMML to LaTeX Converter ────────────────────────────────────────────────

# XML namespaces for OMML
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NSMAP = {"m": MATH_NS}


def _tag(name):
    return f"{{{MATH_NS}}}{name}"


def _get_text(elem):
    """Extract text content from m:r/m:t elements."""
    texts = []
    for t in elem.iter(_tag("t")):
        if t.text:
            texts.append(t.text)
    return "".join(texts)


def _convert_element(elem):
    """Recursively convert an OMML element to LaTeX string."""
    tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

    if tag_name == "r":
        # Run: extract text
        return _get_text(elem)

    elif tag_name == "t":
        return elem.text or ""

    elif tag_name == "f":
        # Fraction
        num_elem = elem.find(_tag("num"))
        den_elem = elem.find(_tag("den"))
        num_text = _convert_element(num_elem) if num_elem is not None else ""
        den_text = _convert_element(den_elem) if den_elem is not None else ""
        return f"\\frac{{{num_text}}}{{{den_text}}}"

    elif tag_name == "rad":
        # Radical (sqrt)
        deg_elem = elem.find(_tag("deg"))
        e_elem = elem.find(_tag("e"))
        e_text = _convert_element(e_elem) if e_elem is not None else ""
        if deg_elem is not None:
            deg_text = _convert_element(deg_elem)
            return f"\\sqrt[{deg_text}]{{{e_text}}}"
        return f"\\sqrt{{{e_text}}}"

    elif tag_name == "sSup":
        # Superscript
        e_elem = elem.find(_tag("e"))
        sup_elem = elem.find(_tag("sup"))
        base = _convert_element(e_elem) if e_elem is not None else ""
        sup = _convert_element(sup_elem) if sup_elem is not None else ""
        if len(base) > 1 or _has_compound(base):
            base = f"{{{base}}}"
        return f"{base}^{{{sup}}}"

    elif tag_name == "sSub":
        # Subscript
        e_elem = elem.find(_tag("e"))
        sub_elem = elem.find(_tag("sub"))
        base = _convert_element(e_elem) if e_elem is not None else ""
        sub = _convert_element(sub_elem) if sub_elem is not None else ""
        if len(base) > 1 or _has_compound(base):
            base = f"{{{base}}}"
        return f"{base}_{{{sub}}}"

    elif tag_name == "sSubSup":
        # Subscript + Superscript
        e_elem = elem.find(_tag("e"))
        sub_elem = elem.find(_tag("sub"))
        sup_elem = elem.find(_tag("sup"))
        base = _convert_element(e_elem) if e_elem is not None else ""
        sub = _convert_element(sub_elem) if sub_elem is not None else ""
        sup = _convert_element(sup_elem) if sup_elem is not None else ""
        if len(base) > 1 or _has_compound(base):
            base = f"{{{base}}}"
        return f"{base}_{{{sub}}}^{{{sup}}}"

    elif tag_name == "nary":
        # N-ary operator: sum, prod, integral, etc.
        chr_elem = elem.find(_tag("chr"))
        sub_elem = elem.find(_tag("sub"))
        sup_elem = elem.find(_tag("sup"))
        e_elem = elem.find(_tag("e"))

        op_char = "\\sum"
        if chr_elem is not None:
            char_attr = chr_elem.get("m:val", "")
            char_map = {
                "\u2211": "\\sum",
                "\u220f": "\\prod",
                "\u222b": "\\int",
                "\u222c": "\\iint",
                "\u222d": "\\iiint",
                "\u222e": "\\oint",
                "\u22c3": "\\bigcup",
                "\u22c2": "\\bigcap",
                "\u2a01": "\\bigoplus",
                "\u2a06": "\\bigotimes",
                "\u22c0": "\\bigwedge",
                "\u22c1": "\\bigvee",
            }
            op_char = char_map.get(char_attr, "\\sum")

        sub_text = _convert_element(sub_elem) if sub_elem is not None else ""
        sup_text = _convert_element(sup_elem) if sup_elem is not None else ""
        e_text = _convert_element(e_elem) if e_elem is not None else ""

        parts = [op_char]
        if sub_text:
            parts.append(f"_{{{sub_text}}}")
        if sup_text:
            parts.append(f"^{{{sup_text}}}")
        if e_text:
            parts.append(f"{{{e_text}}}")
        return "".join(parts)

    elif tag_name == "d":
        # Delimiter (brackets)
        dPr = elem.find(_tag("dPr"))
        e_elem = elem.find(_tag("e"))

        left = "("
        right = ")"
        if dPr is not None:
            beg = dPr.find(_tag("begChr"))
            end = dPr.find(_tag("endChr"))
            if beg is not None:
                left = beg.get("m:val", "(")
            if end is not None:
                right = end.get("m:val", ")")

        # Map common delimiters
        delim_map = {
            "(": "(", ")": ")",
            "[": "[", "]": "]",
            "{": "\\{", "}": "\\}",
            "|": "|",
            "\u2016": "\\|",  # double vertical
            "\u230A": "\\lfloor", "\u230B": "\\rfloor",
            "\u2308": "\\lceil", "\u2309": "\\rceil",
            "\u27E8": "\\langle", "\u27E9": "\\rangle",
        }
        left = delim_map.get(left, left)
        right = delim_map.get(right, right)

        e_text = _convert_element(e_elem) if e_elem is not None else ""
        return f"\\left{left} {e_text} \\right{right}"

    elif tag_name == "acc":
        # Accent (hat, tilde, bar, etc.)
        chr_elem = elem.find(_tag("chr"))
        e_elem = elem.find(_tag("e"))
        e_text = _convert_element(e_elem) if e_elem is not None else ""

        accent_map = {
            "\u0302": "\\hat",
            "\u0303": "\\tilde",
            "\u0304": "\\bar",
            "\u0305": "\\overline",
            "\u0306": "\\breve",
            "\u0307": "\\dot",
            "\u0308": "\\ddot",
            "\u0300": "\\grave",
            "\u0301": "\\acute",
            "\u030C": "\\check",
            "\u20D7": "\\vec",
        }
        if chr_elem is not None:
            char_val = chr_elem.get("m:val", "")
            cmd = accent_map.get(char_val, "\\hat")
            return f"{cmd}{{{e_text}}}"
        return f"\\hat{{{e_text}}}"

    elif tag_name == "bar":
        # Bar (overbar/underbar)
        pos = elem.find(_tag("barPr"))
        e_elem = elem.find(_tag("e"))
        e_text = _convert_element(e_elem) if e_elem is not None else ""
        return f"\\overline{{{e_text}}}"

    elif tag_name == "groupChr":
        # Group character (overbrace, underbrace)
        chr_elem = elem.find(_tag("chr"))
        e_elem = elem.find(_tag("e"))
        e_text = _convert_element(e_elem) if e_elem is not None else ""
        if chr_elem is not None:
            char_val = chr_elem.get("m:val", "")
            if "\u23DE" in char_val:
                return f"\\overbrace{{{e_text}}}"
            if "\u23DF" in char_val:
                return f"\\underbrace{{{e_text}}}"
        return e_text

    elif tag_name == "eqArr":
        # Equation array (aligned equations)
        rows = []
        for row in elem.findall(_tag("e")):
            rows.append(_convert_element(row))
        return " \\\\ ".join(rows)

    elif tag_name == "m":
        # Matrix
        rows = []
        for row in elem.findall(_tag("mr")):
            cols = []
            for cell in row.findall(_tag("e")):
                cols.append(_convert_element(cell))
            rows.append(" & ".join(cols))
        body = " \\\\ ".join(rows)
        return f"\\begin{{matrix}} {body} \\end{{matrix}}"

    elif tag_name == "limLow":
        # Lower limit (e.g., \lim_{x \to 0})
        e_elem = elem.find(_tag("e"))
        lim_elem = elem.find(_tag("lim"))
        base = _convert_element(e_elem) if e_elem is not None else ""
        lim = _convert_element(lim_elem) if lim_elem is not None else ""
        return f"{base}_{{{lim}}}"

    elif tag_name == "limUpp":
        # Upper limit
        e_elem = elem.find(_tag("e"))
        lim_elem = elem.find(_tag("lim"))
        base = _convert_element(e_elem) if e_elem is not None else ""
        lim = _convert_element(lim_elem) if lim_elem is not None else ""
        return f"{base}^{{{lim}}}"

    elif tag_name == "func":
        # Function
        name_elem = elem.find(_tag("fName"))
        e_elem = elem.find(_tag("e"))
        name = _convert_element(name_elem) if name_elem is not None else ""
        arg = _convert_element(e_elem) if e_elem is not None else ""
        func_map = {
            "sin": "\\sin", "cos": "\\cos", "tan": "\\tan",
            "log": "\\log", "ln": "\\ln", "lim": "\\lim",
            "max": "\\max", "min": "\\min",
            "det": "\\det", "dim": "\\dim", "ker": "\\ker",
        }
        cmd = func_map.get(name.strip().lower(), f"\\operatorname{{{name}}}")
        return f"{cmd}{{{arg}}}"

    elif tag_name == "box":
        e_elem = elem.find(_tag("e"))
        if e_elem is not None:
            return _convert_element(e_elem)
        return ""

    elif tag_name == "phant":
        # Phantom element
        e_elem = elem.find(_tag("e"))
        if e_elem is not None:
            content = _convert_element(e_elem)
            return f"\\phantom{{{content}}}"
        return ""

    # Generic: process all children
    parts = []
    for child in elem:
        part = _convert_element(child)
        if part is not None:
            parts.append(part)
    if elem.text and elem.text.strip():
        parts.insert(0, elem.text.strip())
    return " ".join(parts)


def _has_compound(text):
    """Check if text contains LaTeX commands (compound expression)."""
    return bool(re.search(r"\\[a-zA-Z]+", text))


def omml_to_latex(elem):
    """Convert an OMML math element to LaTeX string."""
    # elem is the <m:oMath> or <m:oMathPara> element
    parts = []
    for child in elem:
        # Skip m:oMathPr (math properties)
        if child.tag == _tag("oMathPr") or child.tag.endswith("Pr"):
            continue
        part = _convert_element(child)
        if part:
            parts.append(part)
    return " ".join(parts).strip()


def extract_from_docx(filepath):
    """Extract OMML formulas from a DOCX file and return list of LaTeX strings."""
    try:
        from docx import Document
    except ImportError:
        print("Error: python-docx is required. Install with: pip install python-docx")
        sys.exit(1)

    doc = Document(filepath)
    formulas = []

    # Access the raw XML from the document part
    xml_body = doc.element.body

    # Find all OMML math elements
    for omath in xml_body.iter(_tag("oMath")):
        latex = omml_to_latex(omath)
        if latex:
            formulas.append(latex)

    for omathpara in xml_body.iter(_tag("oMathPara")):
        for omath in omathpara.iter(_tag("oMath")):
            latex = omml_to_latex(omath)
            if latex:
                formulas.append(latex)

    return formulas


# ── PDF Extraction via Mathpix ─────────────────────────────────────────────

def extract_from_pdf(filepath, mathpix_api_key=None, page_range=None):
    """Extract formulas from PDF using Mathpix API."""
    try:
        import fitz  # pymupdf
    except ImportError:
        print("Error: pymupdf is required for PDF extraction. Install with: pip install pymupdf")
        sys.exit(1)

    import json
    import urllib.request
    import urllib.error

    if not mathpix_api_key:
        mathpix_api_key = os.environ.get("MATHPIX_API_KEY", "")
    if not mathpix_api_key:
        print("Warning: No Mathpix API key provided. Set MATHPIX_API_KEY environment variable")
        print("         or use --mathpix-api-key argument.")
        print("         Get a key at https://mathpix.com")
        print("         Falling back to extracting formula regions as images only.")
        return _extract_pdf_formula_regions(filepath, page_range)

    doc = fitz.open(filepath)
    total_pages = doc.page_count

    if page_range:
        start, end = page_range
        start = max(1, start)
        end = min(total_pages, end)
    else:
        start, end = 1, total_pages

    formulas = []

    for page_num in range(start - 1, end):
        page = doc[page_num]

        # Render page to image
        mat = fitz.Matrix(2, 2)  # 2x zoom for better recognition
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        # Encode as base64 for Mathpix API
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        # Call Mathpix API
        api_url = "https://api.mathpix.com/v3/text"
        headers = {
            "app_id": mathpix_api_key,
            "app_key": mathpix_api_key,
            "Content-Type": "application/json",
        }
        data = json.dumps({
            "src": f"data:image/png;base64,{img_b64}",
            "formats": ["latex_styled"],
            "data_options": {"include_latex": True},
        }).encode("utf-8")

        try:
            req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            if "latex_styled" in result:
                latex_text = result["latex_styled"]
                # Split multi-formula output by double backslash or $$ delimiters
                for line in latex_text.split("\\\n"):
                    line = line.strip()
                    if line:
                        formulas.append(line)
            elif "text" in result:
                formulas.append(result["text"])

        except urllib.error.HTTPError as e:
            print(f"  Page {page_num + 1}: HTTP error {e.code} - {e.reason}")
        except Exception as e:
            print(f"  Page {page_num + 1}: Error - {e}")

    doc.close()
    return formulas


def _extract_pdf_formula_regions(filepath, page_range=None):
    """Extract formula regions from PDF as image references (no Mathpix)."""
    import fitz

    doc = fitz.open(filepath)
    total_pages = doc.page_count

    if page_range:
        start, end = page_range
    else:
        start, end = 1, total_pages

    formulas = []
    print(f"Extracting formula regions from pages {start}-{end}...")

    for page_num in range(start - 1, end):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if block.get("type") == 1:  # Image block
                formulas.append(f"[Image formula on page {page_num + 1}]")

    doc.close()
    return formulas


# ── Output Generation ──────────────────────────────────────────────────────

def create_formula_docx(formulas, output_path, source_name):
    """Create a Word document with extracted formulas in a table."""
    try:
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        print("Error: python-docx is required. Install with: pip install python-docx")
        sys.exit(1)

    doc = Document()

    # Title
    title = doc.add_heading(f"Formula Extraction: {source_name}", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph(f"Total formulas extracted: {len(formulas)}")
    doc.add_paragraph("")

    if not formulas:
        doc.add_paragraph("No formulas were found in the document.")
        doc.save(output_path)
        return

    # Create table
    table = doc.add_table(rows=len(formulas) + 1, cols=2, style="Table Grid")
    table.autofit = True

    # Header row
    header_cells = table.rows[0].cells
    header_cells[0].text = "#"
    header_cells[1].text = "LaTeX Formula"
    for cell in header_cells:
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.bold = True

    # Formula rows
    for i, formula in enumerate(formulas, 1):
        row_cells = table.rows[i].cells
        row_cells[0].text = str(i)
        row_cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Write LaTeX code
        latex_para = row_cells[1].paragraphs[0]
        run = latex_para.add_run(formula)
        run.font.name = "Consolas"
        run.font.size = Pt(10)

    # Set column widths
    for row in table.rows:
        row.cells[0].width = Inches(0.5)
        row.cells[1].width = Inches(5.5)

    doc.save(output_path)
    print(f"Output saved to: {output_path}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract mathematical formulas from literature and convert to LaTeX"
    )
    parser.add_argument("source", help="Path to source file (PDF or DOCX)")
    parser.add_argument(
        "--method", choices=["auto", "omml", "mathpix"], default="auto",
        help="Extraction method (default: auto)"
    )
    parser.add_argument("--mathpix-api-key", help="Mathpix API key for PDF extraction")
    parser.add_argument("--output-dir", help="Output directory (default: same as source)")
    parser.add_argument(
        "--page-range", help="Page range for PDF extraction, e.g. 1-10"
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: File not found: {args.source}")
        sys.exit(1)

    ext = source_path.suffix.lower()
    source_name = source_path.stem

    # Determine output path
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = source_path.parent

    output_path = output_dir / f"{source_name}_公式提取.docx"

    # Parse page range
    page_range = None
    if args.page_range:
        match = re.match(r"(\d+)-(\d+)", args.page_range)
        if match:
            page_range = (int(match.group(1)), int(match.group(2)))

    formulas = []

    if ext == ".docx":
        print(f"Extracting formulas from DOCX: {source_path}")
        formulas = extract_from_docx(str(source_path))
    elif ext == ".pdf":
        print(f"Extracting formulas from PDF: {source_path}")
        formulas = extract_from_pdf(
            str(source_path),
            mathpix_api_key=args.mathpix_api_key,
            page_range=page_range,
        )
    else:
        print(f"Error: Unsupported file format: {ext}")
        print("Supported formats: PDF, DOCX")
        sys.exit(1)

    print(f"Found {len(formulas)} formula(s)")

    # Create output
    create_formula_docx(formulas, str(output_path), source_name)

    # Print formulas to stdout as well
    print("\n" + "=" * 60)
    for i, f in enumerate(formulas, 1):
        print(f"[{i}] {f}")


if __name__ == "__main__":
    main()
