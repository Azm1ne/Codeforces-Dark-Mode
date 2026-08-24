#!/usr/bin/env python3
"""Assert every text colour in dark.css is readable on the theme's surfaces.

The whole point of this extension is contrast, so that is what gets tested:
each `color:` declaration must clear WCAG AA (4.5:1) against --bg-tertiary,
the lightest of the three dark surfaces. Clearing the lightest one clears
the other two as well.

Run: python3 tools/check-contrast.py
"""
import pathlib
import re
import sys

CSS = pathlib.Path(__file__).resolve().parent.parent / "dark.css"
AA = 4.5

# Colours that are deliberately not body text on a dark surface.
EXEMPT = {
    "mark",          # its own amber background
    "::selection",   # its own blue background
}


def parse_vars(css):
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*;", css))


def to_rgb(value):
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb):
    def chan(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg, bg):
    a, b = luminance(fg), luminance(bg)
    lo, hi = sorted((a, b))
    return (hi + 0.05) / (lo + 0.05)


def main():
    css = CSS.read_text()
    variables = parse_vars(css)
    surface = to_rgb(variables["--bg-tertiary"])

    failures = []
    checked = 0
    # Each rule: capture its selector list and its `color:` declarations.
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        selectors = " ".join(selectors.split())
        if any(e in selectors for e in EXEMPT):
            continue
        for value in re.findall(r"(?<!-)\bcolor\s*:\s*([^;!]+)", body):
            value = value.strip()
            if value.startswith("var("):
                name = value[4:].split(")")[0].strip()
                value = variables.get(name)
                if value is None:
                    continue
            if not value.startswith("#"):
                continue
            checked += 1
            r = ratio(to_rgb(value), surface)
            if r < AA:
                failures.append(f"  {selectors[:60]:60s} {value}  {r:.2f}:1")

    surface_hex = variables["--bg-tertiary"]
    if failures:
        print(f"FAIL — {len(failures)} colour(s) below {AA}:1 on {surface_hex}:")
        print("\n".join(failures))
        return 1
    print(f"OK — {checked} text colours all clear {AA}:1 on {surface_hex}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
