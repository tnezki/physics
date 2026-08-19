from pathlib import Path
import re
import sys

# ── CONFIGURE ───────────────────────────────────────────────────────────────
# Default: folder this script lives in.
# Optional command-line override:
#   python fix_mathjax_v2.py /absolute/path/to/folder
TARGET_FOLDER = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path(__file__).parent
# ────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — BYTE-LEVEL AUTO-FIXES
# Control-character corruptions where a Python escape sequence replaced the
# backslash in a LaTeX command with a single control-character byte.
# ══════════════════════════════════════════════════════════════════════════════

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

    # ── Dropped-backslash corruptions ───────────────────────────────────────
    (b"\\rac{",     b"\\frac{",   r"\frac  — dropped backslash: \rac{ found"),
    (b"\\ight",     b"\\right",  r"\right — dropped backslash: \ight found"),
]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — REGEX-LEVEL AUTO-FIXES
# Wrong MathJax delimiters in content. JS config escapes are intentionally
# skipped by the negative lookbehind.
# ══════════════════════════════════════════════════════════════════════════════

REGEX_FIXES = [
    (re.compile(rb'(?<!\\)\\\('), b'$',
     r"\( → $ — wrong inline-open delimiter"),
    (re.compile(rb'(?<!\\)\\\)'), b'$',
     r"\) → $ — wrong inline-close delimiter"),
    (re.compile(rb'(?<!\\)\\\['), b'$$',
     r"\[ → $$ — wrong display-open delimiter"),
    (re.compile(rb'(?<!\\)\\\]'), b'$$',
     r"\] → $$ — wrong display-close delimiter"),
]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — MATH-BLOCK-SCOPED AUTO-FIXES  (NEW IN V2)
# These repairs ONLY run inside $...$ and $$...$$ blocks.
# This is intentionally safer than globally changing backslashes or < / >.
# ══════════════════════════════════════════════════════════════════════════════

# Finds display math first, then inline math. Escaped dollar signs are ignored.
MATH_BLOCK_RE = re.compile(
    r'(?<!\\)\$\$(.*?)(?<!\\)\$\$|(?<!\\)\$(?!\$)(.*?)(?<!\\)\$(?!\$)',
    re.DOTALL,
)

# A browser/HTML parser can serialize raw comparison text such as
#   $a<b\\rightarrow -a>-b$
# into something like
#   $a<b\\rightarrow -a="">-b$</b\\rightarrow>
# if the file was parsed and re-serialized before MathJax saw it.
# This pattern reconstructs the intended comparison BEFORE normal math repairs.
SERIALIZED_COMPARISON_RE = re.compile(
    r'(?P<prefix>\$(?:[^$]|\\\$)*?)'
    r'<(?P<tag>[A-Za-z][^\s>$]*)(?:\s+(?P<attrs>[^>$]*))?>'
    r'(?P<body>[^$]*)\$'
    r'(?P<close></[^>]+>)',
    re.DOTALL,
)


def _clean_serialized_attrs(attrs):
    """Undo the common HTML serializer artifact x="" -> x inside math."""
    if not attrs:
        return ''
    cleaned = re.sub(r'([A-Za-z0-9_+\-]+)=(?:""|\'\')', r'\1', attrs)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def repair_serialized_comparisons(text):
    hits = 0

    def repl(match):
        nonlocal hits
        hits += 1
        prefix = match.group('prefix')
        tag = match.group('tag')
        attrs = _clean_serialized_attrs(match.group('attrs'))
        body = match.group('body')
        middle = tag + ((' ' + attrs) if attrs else '')
        # Keep the opening $ already present in prefix and rebuild the relation.
        return f"{prefix}\\lt {middle}\\gt {body}$"

    new_text = SERIALIZED_COMPARISON_RE.sub(repl, text)
    return new_text, hits


def repair_math_blocks(text):
    r"""
    Repair only the CONTENT of MathJax dollar-delimited blocks.

    V2 fixes:
      • doubled TeX command slashes:  \\frac -> \frac
      • HTML entities in math:        &lt; -> \lt, &gt; -> \gt
      • raw comparison signs in math: < -> \lt, > -> \gt
      • literal tabs in math:         tab -> \qquad

    Returns (new_text, list_of_human_readable_hit_strings).
    """
    counts = {
        'double_tex': 0,
        'lt_entity': 0,
        'gt_entity': 0,
        'raw_lt': 0,
        'raw_gt': 0,
        'tabs': 0,
    }

    def repl(match):
        whole = match.group(0)
        delim = '$$' if whole.startswith('$$') else '$'
        content = whole[len(delim):-len(delim)]

        # 1) Literal tab characters are never useful TeX commands inside math.
        tab_count = content.count('\t')
        if tab_count:
            content = content.replace('\t', r'\qquad ')
            counts['tabs'] += tab_count

        # 2) Collapse two literal backslashes before an alphabetic TeX command.
        #    Scope is ONLY inside math, avoiding JS config and normal HTML.
        pattern = re.compile(r'\\\\(?=[A-Za-z])')
        n = len(pattern.findall(content))
        if n:
            content = pattern.sub(lambda _: '\\', content)
            counts['double_tex'] += n

        # 3) Normalize HTML entities used as relations inside math.
        n = content.count('&lt;') + content.count('&#60;') + content.count('&#x3c;') + content.count('&#x3C;')
        if n:
            content = (content.replace('&lt;', r'\lt')
                              .replace('&#60;', r'\lt')
                              .replace('&#x3c;', r'\lt')
                              .replace('&#x3C;', r'\lt'))
            counts['lt_entity'] += n

        n = content.count('&gt;') + content.count('&#62;') + content.count('&#x3e;') + content.count('&#x3E;')
        if n:
            content = (content.replace('&gt;', r'\gt')
                              .replace('&#62;', r'\gt')
                              .replace('&#x3e;', r'\gt')
                              .replace('&#x3E;', r'\gt'))
            counts['gt_entity'] += n

        # 4) Raw < and > are unsafe in HTML source inside math. Convert them.
        n = content.count('<')
        if n:
            content = content.replace('<', r'\lt ')
            counts['raw_lt'] += n

        n = content.count('>')
        if n:
            content = content.replace('>', r'\gt ')
            counts['raw_gt'] += n

        return f'{delim}{content}{delim}'

    new_text = MATH_BLOCK_RE.sub(repl, text)

    hits = []
    if counts['double_tex']:
        hits.append(f"         {counts['double_tex']}× doubled TeX command slash collapsed inside math")
    if counts['tabs']:
        hits.append(f"         {counts['tabs']}× literal tab in math replaced with \\qquad")
    if counts['lt_entity']:
        hits.append(f"         {counts['lt_entity']}× &lt; entity in math normalized to \\lt")
    if counts['gt_entity']:
        hits.append(f"         {counts['gt_entity']}× &gt; entity in math normalized to \\gt")
    if counts['raw_lt']:
        hits.append(f"         {counts['raw_lt']}× raw < in math normalized to \\lt")
    if counts['raw_gt']:
        hits.append(f"         {counts['raw_gt']}× raw > in math normalized to \\gt")

    return new_text, hits


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — AUDIT CHECKS (report only — do NOT auto-fix)
# ══════════════════════════════════════════════════════════════════════════════

def audit_file(path, text):
    warnings = []

    # Identify math spans first so a valid expression such as $12-3x$ is
    # not falsely reported as currency merely because it starts with a digit.
    math_matches = list(MATH_BLOCK_RE.finditer(text))
    math_blocks = [m.group(0) for m in math_matches]
    math_spans = [m.span() for m in math_matches]

    def inside_math(pos):
        return any(a <= pos < b for a, b in math_spans)

    # Bare currency $[digit] in prose (breaks MathJax on that item).
    bare_positions = [
        m.start() for m in re.finditer(r'(?<!\\)(?<!\$)\$(?!\$)\d', text)
        if not inside_math(m.start())
    ]
    if bare_positions:
        warnings.append(
            f"    BARE CURRENCY: {len(bare_positions)} instance(s) of $[digit] outside math — use \\$N in prose"
        )

    # Raw < or > inside math delimiters should be gone after V2 auto-fix.
    raw_angle = sum(1 for b in math_blocks if '<' in b or '>' in b)
    if raw_angle:
        warnings.append(f"    RAW < or > IN MATH: {raw_angle} math block(s) remain")

    # Doubled TeX command slashes should also be gone after V2 auto-fix.
    doubled = sum(len(re.findall(r'\\\\(?=[A-Za-z])', b)) for b in math_blocks)
    if doubled:
        warnings.append(f"    DOUBLED TEX ESCAPE: {doubled} instance(s) remain inside math")

    # Suspicious HTML tag residue touching a math block.
    serialized = len(SERIALIZED_COMPARISON_RE.findall(text))
    if serialized:
        warnings.append(f"    SERIALIZED COMPARISON ARTIFACT: {serialized} suspicious math/HTML tag pattern(s) remain")

    # Wrong CDN
    if 'mathjax' in text.lower():
        if 'cdnjs' in text or 'unpkg' in text:
            warnings.append("    WRONG CDN: use cdn.jsdelivr.net")

    # MathJax config after CDN
    config_pos = text.find('window.MathJax')
    cdn_pos = text.find('cdn.jsdelivr.net')
    if config_pos != -1 and cdn_pos != -1 and config_pos > cdn_pos:
        warnings.append("    HEAD ORDER: window.MathJax config appears AFTER the CDN script")

    return warnings


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

folder = Path(TARGET_FOLDER)
html_files = [p for p in folder.rglob('*.html') if p.is_file()]

if not html_files:
    print(f"No HTML files found in: {folder.resolve()}")
else:
    print(f"Scanning {len(html_files)} HTML file(s) in: {folder.resolve()}\n")

fixed_count = 0
audit_count = 0

for path in html_files:
    raw = path.read_bytes()
    new_raw = raw
    hits = []

    # Section 1 — byte-level fixes
    for corrupt, replacement, label in FIXES:
        count = new_raw.count(corrupt)
        if count:
            new_raw = new_raw.replace(corrupt, replacement)
            hits.append(f"         {count}× {label}")

    # Section 2 — regex-level delimiter fixes
    for pattern, replacement, label in REGEX_FIXES:
        count = len(pattern.findall(new_raw))
        if count:
            new_raw = pattern.sub(replacement, new_raw)
            hits.append(f"         {count}× {label}")

    # Decode once for scoped V2 repairs.
    text = new_raw.decode('utf-8', errors='replace')

    # Section 3a — repair parser-serialized raw-comparison corruption.
    text, serialized_hits = repair_serialized_comparisons(text)
    if serialized_hits:
        hits.append(f"         {serialized_hits}× serialized comparison artifact reconstructed")

    # Section 3b — repair MathJax content only.
    text, math_hits = repair_math_blocks(text)
    hits.extend(math_hits)
    new_raw = text.encode('utf-8')

    if hits:
        path.write_bytes(new_raw)
        print(f"  FIXED  {path}")
        for h in hits:
            print(h)
        fixed_count += 1

    # Section 4 — audit after all repairs
    warnings = audit_file(path, text)
    if warnings:
        if not hits:
            print(f"  AUDIT  {path}")
        else:
            print("  ↳ AUDIT warnings:")
        for w in warnings:
            print(w)
        audit_count += 1
    elif not hits:
        print(f"  ok     {path}")

print(f"\nDone. {fixed_count} file(s) auto-fixed. {audit_count} file(s) have audit warnings.")
