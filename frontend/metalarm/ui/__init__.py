"""MetalArm's component library (overhaul, Section 5).

Every component here reads metalarm/theme.py tokens only - no hex colour, raw
type size or radius is written in this package (frontend/tests/test_tokens.py
enforces it). Each one renders its states - default, selected, disabled,
skeleton, empty - and appears on the hidden /gallery page at phone widths.

Components take plain values or Reflex Vars; `when()` picks between the two
kinds of condition so the same component serves the gallery and live state.
"""
