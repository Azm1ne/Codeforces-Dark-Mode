#!/usr/bin/env python3
"""Check dark.css for the two things that silently break this theme.

1. Contrast — each `color:` declaration must clear WCAG AA (4.5:1) against
   --bg-tertiary, the lightest of the three dark surfaces. Clearing the
   lightest one clears the other two as well.

2. Link specificity — no rule colouring plain anchors may outrank the
   `.user-*` rank-colour rules. Writing `a:link` instead of `a` scores
   (0,1,1) against their (0,1,0) and repaints every handle on the site
   link-blue. That shipped once; this catches it.

Run: python3 tools/check-theme.py
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


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


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


def specificity(selector):
    """(ids, classes, elements) for one selector. Good enough for this file:
    :not(...) contributes its argument's specificity, pseudo-elements do not."""
    sel = re.sub(r":not\(([^)]*)\)", r" \1 ", selector)
    sel = re.sub(r"::[\w-]+", " ", sel)
    ids = len(re.findall(r"#[\w-]+", sel))
    classes = len(re.findall(r"\.[\w-]+", sel)) + len(re.findall(r":[\w-]+", sel))
    classes += len(re.findall(r"\[[^\]]*\]", sel))
    elements = len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][\w-]*)", sel))
    return (ids, classes, elements)


def check_link_specificity(rules):
    """Anchor colour rules must lose to the rank-colour rules."""
    anchors, ranks = [], []
    for selectors, body in rules:
        if not re.search(r"(?<!-)\bcolor\s*:", body):
            continue
        for sel in selectors.split(","):
            sel = sel.strip()
            if not sel:
                continue
            if ".user-" in sel:
                ranks.append((sel, specificity(sel)))
            elif re.fullmatch(r"a(:[\w-]+(\([^)]*\))?)*", sel):
                excluded = re.findall(r":not\(([^)]*)\)", sel)
                if any("rated-user" in e or "user-" in e for e in excluded):
                    continue  # explicitly skips handles, so it cannot clobber them
                anchors.append((sel, specificity(sel)))

    if not anchors or not ranks:
        return [f"expected both anchor and .user-* colour rules, found "
                f"{len(anchors)} and {len(ranks)}"]

    weakest_rank = min(s for _, s in ranks)
    return [f"  `{sel}` scores {spec} and outranks the rank colours at "
            f"{weakest_rank} — handles would render link-blue"
            for sel, spec in anchors if spec >= weakest_rank]


def main():
    css = strip_comments(CSS.read_text())
    variables = parse_vars(css)
    surface = to_rgb(variables["--bg-tertiary"])

    rules = [(" ".join(s.split()), b)
             for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]

    failures = []
    checked = 0
    for selectors, body in rules:
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
    ok = True
    if failures:
        print(f"FAIL — {len(failures)} colour(s) below {AA}:1 on {surface_hex}:")
        print("\n".join(failures))
        ok = False
    else:
        print(f"OK — {checked} text colours all clear {AA}:1 on {surface_hex}")

    link_failures = check_link_specificity(rules)
    if link_failures:
        print("FAIL — anchor colour rules outrank the rank colours:")
        print("\n".join(link_failures))
        ok = False
    else:
        print("OK — anchor colour rules lose to the .user-* rank colours")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
