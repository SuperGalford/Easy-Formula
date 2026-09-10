from easy_formula.text_latex import unicode_math_to_latex


def test_unicode_conversion():
    out = unicode_math_to_latex("β ≤ α + x²")
    assert r"\beta" in out
    assert r"\leq" in out
    assert r"\alpha" in out
    assert "^{2}" in out


def test_remove_equation_number():
    out = unicode_math_to_latex("x = y (12)")
    assert "(12)" not in out
