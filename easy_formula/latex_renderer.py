from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def latex_compile_check(latex: str, timeout: int = 12) -> tuple[bool, str]:
    engine = shutil.which("pdflatex")
    if not engine:
        return True, "未找到 pdflatex，已跳过编译检查。"

    document = r"""\documentclass{article}
\usepackage{amsmath,amssymb,bm,mathtools}
\pagestyle{empty}
\begin{document}
\[
%s
\]
\end{document}
""" % latex
    with tempfile.TemporaryDirectory(prefix="easy_formula_latex_") as td:
        td_path = Path(td)
        tex = td_path / "formula.tex"
        tex.write_text(document, encoding="utf-8")
        try:
            proc = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", tex.name],
                cwd=td_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return False, "LaTeX 编译检查超时。"
        if proc.returncode == 0:
            return True, "LaTeX 编译通过。"
        tail = "\n".join(proc.stdout.splitlines()[-8:])
        return False, tail
