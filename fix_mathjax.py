from pathlib import Path
import re

# ── CONFIGURE ───────────────────────────────────────────────────────────────
# Defaults to the folder this script lives in. Override with an absolute path:
#   TARGET_FOLDER = r"/Users/troynezki/Downloads/friday/algebra/zzzz-resources/structure"
TARGET_FOLDER = Path(__file__).parent
# ────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — BYTE-LEVEL AUTO-FIXES
# Control-character corruptions where a Python escape sequence replaced the
# backslash in a LaTeX command with a single control-character byte.
# ══════════════════════════════════════════════════════════════════════════════
#
# HOW TO ADD A NEW FIX:
#   1. Identify the corrupt byte: grep -Pn "\xNN" file.html | cat -A
#   2. Add a tuple: (corrupt_bytes, fixed_bytes, "description")
#
# FORMAT:  (b"corrupt", b"correct", "description")

FIXES = [

    # ── CONFIRMED IN PRODUCTION ─────────────────────────────────────────────
    (b"\x0crac{",   b"\\frac{",   r"\frac  — 0x0C formfeed  replaces \f before rac{"),
    (b"\x0corall",  b"\\forall",  r"\forall— 0x0C formfeed  replaces \f before orall"),

    # ── Backspace (0x08) — \begin ────────────────────────────────────────────
    (b"\x08egin{",  b"\\begin{",  r"\begin — 0x08 backspace replaces \b before egin{"),

    # ── Tab (0x09) — \theta \text \times \to ────────────────────────────────
    (b"\x09heta",   b"\\theta",   r"\theta — 0x09 tab       replaces \t before heta"),
    (b"\x09ext{",   b"\\text{",   r"\text  — 0x09 tab       replaces \t before ext{"),
    (b"\x09imes",   b"\\times",   r"\times — 0x09 tab       replaces \t before imes"),
    (b"\x09o ",     b"\\to ",     r"\to    — 0x09 tab       replaces \t before o "),

    # ── CR (0x0D) — \right \rangle ──────────────────────────────────────────
    (b"\x0dight",   b"\\right",   r"\right — 0x0D CR        replaces \r before ight"),
    (b"\x0dangle",  b"\\rangle",  r"\rangle— 0x0D CR        replaces \r before angle"),

    # ── Bell (0x07) — \alpha \angle ─────────────────────────────────────────
    (b"\x07lpha",   b"\\alpha",   r"\alpha — 0x07 bell      replaces \a before lpha"),
    (b"\x07ngle",   b"\\angle",   r"\angle — 0x07 bell      replaces \a before ngle"),

    # ── Vtab (0x0B) — \vec \vee \vdots ─────────────────────────────────────
    (b"\x0bec{",    b"\\vec{",    r"\vec   — 0x0B vtab      replaces \v before ec{"),
    (b"\x0bee",     b"\\vee",     r"\vee   — 0x0B vtab      replaces \v before ee"),
    (b"\x0bdots",   b"\\vdots",   r"\vdots — 0x0B vtab      replaces \v before dots"),

    # ── Dropped-backslash corruptions (\ simply omitted, no control char) ───
    # Source: pass_mathjax.txt Pass 1 + portable_memory_practice_sets.txt
    (b"\\rac{",     b"\\frac{",   r"\frac  — dropped backslash: \rac{ found"),
    (b"\\ight",     b"\\right",   r"\right — dropped backslash: \ight found"),

    # ── ADD NEW BYTE-LEVEL FIXES BELOW THIS LINE ─────────────────────────────
]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — REGEX-LEVEL AUTO-FIXES
# String-pattern fixes that need lookbehind to avoid false matches.
# Applied after Section 1 byte fixes.
# ══════════════════════════════════════════════════════════════════════════════
#
# WHY REGEX HERE (not in FIXES list above):
#   \( and \[ appear in two contexts:
#     — As math delimiters in content:  \(x+1\)   → should become $x+1$
#     — As escaped chars in JS config:  ['\\(','\\)']  → should NOT be touched
#   A plain bytes.replace() can't distinguish these.
#   The negative lookbehind (?<!\\) matches \( only when NOT preceded by \.
#   This correctly skips \\( (config) while fixing \( (content).
#
# SOURCE: pass_mathjax.txt Pass 7, all portable memory MathJax sections.
# Confirmed needed in: zzzz-resources/structure/ (banks, formatives, warmups,
#   activities, notes, summatives, progress trackers — entire older batch).
#
# FORMAT: (compiled_regex, replacement_bytes, "description")

REGEX_FIXES = [

    # ── Wrong MathJax delimiters: \(...\) → $...$ ───────────────────────────
    # \( not preceded by \ → $   (inline open)
    # \) not preceded by \ → $   (inline close)
    (re.compile(rb'(?<!\\)\\\('), b'$',
     r"\( → $ — wrong inline-open delimiter"),
    (re.compile(rb'(?<!\\)\\\)'), b'$',
     r"\) → $ — wrong inline-close delimiter"),

    # ── Wrong MathJax delimiters: \[...\] → $$...$$ ─────────────────────────
    # \[ not preceded by \ → $$  (display open)
    # \] not preceded by \ → $$  (display close)
    (re.compile(rb'(?<!\\)\\\['), b'$$',
     r"\[ → $$ — wrong display-open delimiter"),
    (re.compile(rb'(?<!\\)\\\]'), b'$$',
     r"\] → $$ — wrong display-close delimiter"),

    # ── ADD NEW REGEX FIXES BELOW THIS LINE ──────────────────────────────────
]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — AUDIT CHECKS (report only — do NOT auto-fix)
# ══════════════════════════════════════════════════════════════════════════════

def audit_file(path, text):
    warnings = []

    # Bare currency $[digit] in prose (breaks MathJax on that item)
    bare = re.findall(r'(?<!\\)(?<!\$)\$(?!\$)\d', text)
    if bare:
        warnings.append(f"    BARE CURRENCY: {len(bare)} instance(s) of $[digit] — use \\$N in prose")

    # Raw < or > inside math delimiters → use \lt / \gt
    math_blocks = re.findall(r'\$\$.*?\$\$|\$[^$\n]+?\$', text, re.DOTALL)
    raw_angle = sum(1 for b in math_blocks if '<' in b or '>' in b)
    if raw_angle:
        warnings.append(f"    RAW < or > IN MATH: {raw_angle} math block(s) — use \\lt / \\gt")

    # Wrong CDN
    if 'mathjax' in text.lower():
        if 'cdnjs' in text or 'unpkg' in text:
            warnings.append("    WRONG CDN: use cdn.jsdelivr.net")

    # MathJax config after CDN
    config_pos = text.find('window.MathJax')
    cdn_pos    = text.find('cdn.jsdelivr.net')
    if config_pos != -1 and cdn_pos != -1 and config_pos > cdn_pos:
        warnings.append("    HEAD ORDER: window.MathJax config appears AFTER the CDN script")

    return warnings


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

folder     = Path(TARGET_FOLDER)
html_files = [p for p in folder.rglob("*.html") if p.is_file()]

if not html_files:
    print(f"No HTML files found in: {folder.resolve()}")
else:
    print(f"Scanning {len(html_files)} HTML file(s) in: {folder.resolve()}\n")

fixed_count = 0
audit_count = 0

for path in html_files:
    raw     = path.read_bytes()
    new_raw = raw
    hits    = []

    # Section 1 — byte-level fixes
    for corrupt, replacement, label in FIXES:
        count = new_raw.count(corrupt)
        if count:
            new_raw = new_raw.replace(corrupt, replacement)
            hits.append(f"         {count}× {label}")

    # Section 2 — regex-level fixes
    for pattern, replacement, label in REGEX_FIXES:
        count = len(pattern.findall(new_raw))
        if count:
            new_raw = pattern.sub(replacement, new_raw)
            hits.append(f"         {count}× {label}")

    if hits:
        path.write_bytes(new_raw)
        print(f"  FIXED  {path}")
        for h in hits:
            print(h)
        fixed_count += 1

    # Section 3 — audit
    try:
        text = new_raw.decode('utf-8', errors='replace')
    except Exception:
        text = ""

    warnings = audit_file(path, text)
    if warnings:
        if not hits:
            print(f"  AUDIT  {path}")
        else:
            print(f"  ↳ AUDIT warnings:")
        for w in warnings:
            print(w)
        audit_count += 1
    elif not hits:
        print(f"  ok     {path}")

print(f"\nDone. {fixed_count} file(s) auto-fixed. {audit_count} file(s) have audit warnings.")
