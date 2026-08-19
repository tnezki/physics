from pathlib import Path
import re
import sys
import csv

# ── CONFIGURE ───────────────────────────────────────────────────────────────
# Default: folder this script lives in.
# Optional command-line override:
#   python fix_mathjax_v4.py /absolute/path/to/folder
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
# SECTION 3 — MATH-STRUCTURE + MATH-BLOCK AUTO-FIXES
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



# ─────────────────────────────────────────────────────────────────────────────
# V4 — MALFORMED DOLLAR / ESCAPED-HTML REPAIRS
#
# Two production failures are handled here:
#
#   $f(x)=$1/(x-2)$$
#       -> $f(x)=1/(x-2)$
#
# and HTML tags that were previously swallowed by a malformed math span and
# converted to literal MathJax relations:
#
#   \lt article class="bank-item"\gt
#       -> <article class="bank-item">
#
# Known HTML-tag restoration is deliberately limited to actual structural /
# formatting tag names. Legitimate mathematical \lt and \gt remain untouched.
# ─────────────────────────────────────────────────────────────────────────────

NESTED_INLINE_ASSIGNMENT_RE = re.compile(
    r'\$([^$\n<>]{1,80}?)=\$([^$\n<>]{1,180}?)\$\$'
)

KNOWN_HTML_TAGS = (
    r'article|ol|ul|li|div|p|section|details|summary|header|figure|figcaption|'
    r'table|thead|tbody|tfoot|tr|td|th|span|strong|em|b|i|h[1-6]|dl|dt|dd|img'
)

ESCAPED_HTML_TAG_RE = re.compile(
    rf'\\lt\s*(/?)\s*({KNOWN_HTML_TAGS})\b([^\n]*?)\\gt',
    re.IGNORECASE,
)

INLINE_PRESENTATION_TAG_RE = re.compile(
    r'</?(?:strong|b|em|i|span)(?:\s+[^>]*)?>',
    re.IGNORECASE,
)

BARE_RAC_RE = re.compile(r'(?<![A-Za-z\\])rac\{')


def repair_malformed_math_assignments(text):
    """
    Repair the production typo:
        $f(x)=$1/(x-2)$$
    to:
        $f(x)=1/(x-2)$

    This is intentionally narrow: one inline math assignment accidentally
    contains a second opening $ and ends with $$.
    """
    hits = 0

    def repl(match):
        nonlocal hits
        hits += 1
        return f"${match.group(1)}={match.group(2)}$"

    return NESTED_INLINE_ASSIGNMENT_RE.sub(repl, text), hits


def repair_escaped_html_tags(text):
    """
    Restore known HTML tags that a prior malformed-math cleanup converted to
    literal '\\lt tag ... \\gt' text.

    Only known HTML tags are restored; mathematical \\lt / \\gt expressions
    are not changed.
    """
    hits = 0

    def repl(match):
        nonlocal hits
        hits += 1
        slash = match.group(1)
        tag = match.group(2)
        attrs = match.group(3)

        if slash:
            return f"</{tag}>"
        return f"<{tag}{attrs}>"

    return ESCAPED_HTML_TAG_RE.sub(repl, text), hits


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


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SAFE ALGEBRA-NOTATION CLEANUP
# These repairs target common generated-expression artifacts.
#
# They run on student-facing text, but skip <script> and <style> blocks in HTML.
# Coefficient-1 cleanup is deliberately limited to common lowercase algebra
# variables so units such as 1m, 1s, 1V, and 1A are not silently changed.
# ══════════════════════════════════════════════════════════════════════════════

COEFFICIENT_VARIABLES = "abcdfghjkpqrtuvwxyz"
# Intentionally excludes common unit letters m and s and uppercase unit symbols.
# Includes x, y, z, t, k, p, q, r, etc.

PROTECTED_HTML_RE = re.compile(
    r'(<script\b.*?</script>|<style\b.*?</style>)',
    re.IGNORECASE | re.DOTALL,
)

COEFF_ONE_RE = re.compile(
    rf'(?<![\dA-Za-z_.])([+-]?)1([{COEFFICIENT_VARIABLES}])'
    r'(?=(?:\^|_|[+\-*/=<>),.;:\]}]|\\|$|\s))'
)

PLUS_MINUS_RE = re.compile(
    r'(?<=[A-Za-z0-9}\)])\s*\+\s*-\s*(?=[0-9A-Za-z(\\])'
)

MINUS_MINUS_RE = re.compile(
    r'(?<=[A-Za-z0-9}\)])\s*-\s*-\s*(?=[0-9A-Za-z(\\])'
)


def _repair_algebra_segment(segment):
    counts = {
        'coeff_one': 0,
        'plus_minus': 0,
        'minus_minus': 0,
    }

    def coeff_repl(match):
        counts['coeff_one'] += 1
        sign = match.group(1)
        var = match.group(2)
        return f"{sign}{var}"

    segment = COEFF_ONE_RE.sub(coeff_repl, segment)

    n = len(PLUS_MINUS_RE.findall(segment))
    if n:
        segment = PLUS_MINUS_RE.sub('-', segment)
        counts['plus_minus'] += n

    n = len(MINUS_MINUS_RE.findall(segment))
    if n:
        segment = MINUS_MINUS_RE.sub('+', segment)
        counts['minus_minus'] += n

    return segment, counts


def repair_algebra_notation(text, is_html=False):
    """
    Fix common generated algebra artifacts:
      1x  -> x
     -1x  -> -x
      1t^2 -> t^2
      x+-5 -> x-5
      x--6 -> x+6

    For HTML, <script> and <style> blocks are protected.
    Returns (new_text, human_readable_hits).
    """
    total = {
        'coeff_one': 0,
        'plus_minus': 0,
        'minus_minus': 0,
    }

    if is_html:
        parts = PROTECTED_HTML_RE.split(text)
        out = []
        for part in parts:
            if PROTECTED_HTML_RE.fullmatch(part or ''):
                out.append(part)
                continue
            repaired, counts = _repair_algebra_segment(part)
            out.append(repaired)
            for k in total:
                total[k] += counts[k]
        new_text = ''.join(out)
    else:
        new_text, counts = _repair_algebra_segment(text)
        for k in total:
            total[k] += counts[k]

    hits = []
    if total['coeff_one']:
        hits.append(
            f"         {total['coeff_one']}× coefficient-1 notation simplified "
            "(for example 1x→x or -1x→-x)"
        )
    if total['plus_minus']:
        hits.append(
            f"         {total['plus_minus']}× plus-negative artifact simplified "
            "(for example x+-5→x-5)"
        )
    if total['minus_minus']:
        hits.append(
            f"         {total['minus_minus']}× double-minus artifact simplified "
            "(for example x--6→x+6)"
        )

    return new_text, hits


def repair_math_blocks(text):
    r"""
    Repair only the CONTENT of MathJax dollar-delimited blocks.

    Math-block fixes:
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
        'inline_html_tags': 0,
        'bare_rac': 0,
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

        # 4) Strip harmless presentation tags accidentally placed INSIDE math.
        #    Example: $f(2)=<strong>7</strong>$ -> $f(2)=7$
        n = len(INLINE_PRESENTATION_TAG_RE.findall(content))
        if n:
            content = INLINE_PRESENTATION_TAG_RE.sub('', content)
            counts['inline_html_tags'] += n

        # 5) Repair a dropped \\frac command seen in production:
        #       $- rac{3}{4}$ -> $- \frac{3}{4}$
        n = len(BARE_RAC_RE.findall(content))
        if n:
            content = BARE_RAC_RE.sub(r'\\frac{', content)
            counts['bare_rac'] += n

        # 6) Raw < and > are unsafe in HTML source inside math. Convert them.
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
    if counts['inline_html_tags']:
        hits.append(
            f"         {counts['inline_html_tags']}× presentation HTML tag removed from inside math"
        )
    if counts['bare_rac']:
        hits.append(
            f"         {counts['bare_rac']}× dropped \\frac command repaired from bare rac{{"
        )

    return new_text, hits


def repair_tarsia_delimiters(text):
    """
    Safely repair one common Tarsia export typo:

      $\lim_{x\to\infty}1/x, $0$ from positive infinity
      ->
      $\lim_{x\to\infty}1/x$, $0$ from positive infinity

    Only repairs a line when ALL are true:
      • exactly 3 unescaped dollar signs occur
      • the line begins with math
      • the first comma (Tarsia question/answer separator) appears BEFORE
        the second dollar sign

    Otherwise the line is left alone and the audit will report it.
    """
    out = []
    fixed = 0

    for line in text.splitlines(keepends=True):
        dollars = [m.start() for m in re.finditer(r'(?<!\\)\$', line)]
        comma = line.find(',')

        if (
            len(dollars) == 3
            and line.lstrip().startswith('$')
            and comma != -1
            and comma < dollars[1]
        ):
            line = line[:comma] + '$' + line[comma:]
            fixed += 1

        out.append(line)

    hits = []
    if fixed:
        hits.append(
            f"         {fixed}× malformed Tarsia math delimiter repaired "
            "(missing $ inserted before question/answer comma)"
        )

    return ''.join(out), hits


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — AUDIT CHECKS (report only — do NOT auto-fix)
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

    # Remaining generated-algebra artifacts.
    coeff_left = len(COEFF_ONE_RE.findall(text))
    if coeff_left:
        warnings.append(
            f"    COEFFICIENT-1 ARTIFACT: {coeff_left} instance(s) remain "
            "(for example 1x or -1x)"
        )

    plus_minus_left = len(PLUS_MINUS_RE.findall(text))
    if plus_minus_left:
        warnings.append(
            f"    PLUS-NEGATIVE ARTIFACT: {plus_minus_left} instance(s) remain "
            "(for example x+-5)"
        )

    minus_minus_left = len(MINUS_MINUS_RE.findall(text))
    if minus_minus_left:
        warnings.append(
            f"    DOUBLE-MINUS ARTIFACT: {minus_minus_left} instance(s) remain "
            "(for example x--6)"
        )

    # Delimiter audit. Text exports are line-oriented, so odd counts per line
    # are especially useful for catching malformed Tarsia / CSV math.
    if path.suffix.lower() in {'.txt', '.csv'}:
        bad_lines = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            dollars = len(re.findall(r'(?<!\\)\$', line))
            if dollars % 2:
                bad_lines.append(lineno)
        if bad_lines:
            preview = ", ".join(map(str, bad_lines[:8]))
            if len(bad_lines) > 8:
                preview += ", ..."
            warnings.append(
                f"    UNBALANCED $ DELIMITERS: odd unescaped-$ count on line(s) {preview}"
            )
    elif path.suffix.lower() == '.html':
        dollars = len(re.findall(r'(?<!\\)\$', text))
        if dollars % 2:
            warnings.append(
                "    UNBALANCED $ DELIMITERS: odd unescaped-$ count in HTML file"
            )

    # Malformed nested-dollar assignment should be gone after V4 auto-fix.
    nested_math = len(NESTED_INLINE_ASSIGNMENT_RE.findall(text))
    if nested_math:
        warnings.append(
            f"    MALFORMED NESTED MATH: {nested_math} instance(s) like $f(x)=$...$$ remain"
        )

    # HTML structure must never remain serialized as literal \lt tag \gt text.
    escaped_tags = len(ESCAPED_HTML_TAG_RE.findall(text))
    if escaped_tags:
        warnings.append(
            f"    ESCAPED HTML STRUCTURE: {escaped_tags} known HTML tag(s) remain as \\\\lt ... \\\\gt"
        )

    # Presentation HTML inside math should have been stripped.
    inline_tag_math = 0
    for block in math_blocks:
        inline_tag_math += len(INLINE_PRESENTATION_TAG_RE.findall(block))
    if inline_tag_math:
        warnings.append(
            f"    HTML INSIDE MATH: {inline_tag_math} presentation tag(s) remain inside MathJax blocks"
        )

    # Bare dropped fraction command should be gone after V4 repair.
    bare_rac = 0
    for block in math_blocks:
        bare_rac += len(BARE_RAC_RE.findall(block))
    if bare_rac:
        warnings.append(
            f"    DROPPED FRAC COMMAND: {bare_rac} bare rac{{...}} instance(s) remain inside math"
        )

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
SUPPORTED_SUFFIXES = {'.html', '.txt', '.csv'}
text_files = [
    p for p in folder.rglob('*')
    if p.is_file()
    and p.suffix.lower() in SUPPORTED_SUFFIXES
    and '__MACOSX' not in p.parts
    and not p.name.startswith('._')
]

if not text_files:
    print(f"No supported text files found in: {folder.resolve()}")
else:
    print(
        f"Scanning {len(text_files)} supported file(s) "
        f"(.html/.txt/.csv) in: {folder.resolve()}\n"
    )

fixed_count = 0
audit_count = 0

for path in text_files:
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

    # Section 3a — repair malformed nested inline-math assignments first.
    text, nested_math_hits = repair_malformed_math_assignments(text)
    if nested_math_hits:
        hits.append(
            f"         {nested_math_hits}× malformed nested-dollar assignment repaired"
        )

    # Section 3b — restore known HTML tags that a prior malformed-math pass
    # converted into literal \\lt tag ... \\gt text.
    if path.suffix.lower() == '.html':
        text, escaped_html_hits = repair_escaped_html_tags(text)
        if escaped_html_hits:
            hits.append(
                f"         {escaped_html_hits}× escaped HTML tag restored from \\lt ... \\gt"
            )

    # Section 3c — repair parser-serialized raw-comparison corruption in HTML.
    if path.suffix.lower() == '.html':
        text, serialized_hits = repair_serialized_comparisons(text)
        if serialized_hits:
            hits.append(
                f"         {serialized_hits}× serialized comparison artifact reconstructed"
            )

    # Section 3d — repair MathJax content in any supported text file.
    text, math_hits = repair_math_blocks(text)
    hits.extend(math_hits)

    # Section 4 — clean common generated algebra notation.
    text, algebra_hits = repair_algebra_notation(
        text,
        is_html=(path.suffix.lower() == '.html'),
    )
    hits.extend(algebra_hits)

    # Section 4b — safe Tarsia-only delimiter repair.
    if path.suffix.lower() == '.txt' and path.name.startswith('tarsia_'):
        text, tarsia_hits = repair_tarsia_delimiters(text)
        hits.extend(tarsia_hits)

    new_raw = text.encode('utf-8')

    if hits:
        path.write_bytes(new_raw)
        print(f"  FIXED  {path}")
        for h in hits:
            print(h)
        fixed_count += 1

    # Section 5 — audit after all repairs
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


# ── V4 folder-level Bank structure audit ─────────────────────────────────────
# If a canonical Bank HTML and mapping CSV sit together, compare the number of
# real <article class="bank-item"> elements with mapping rows. This catches the
# exact production failure where malformed math swallowed dozens of HTML cards.

for html_path in [p for p in text_files if p.suffix.lower() == '.html']:
    mapping_candidates = list(html_path.parent.glob('*_mapping.csv'))
    if not mapping_candidates:
        continue

    html_text = html_path.read_text(encoding='utf-8', errors='replace')
    article_count = len(re.findall(
        r'<article\b[^>]*class=["\'][^"\']*\bbank-item\b[^>]*>',
        html_text,
        flags=re.IGNORECASE,
    ))

    for mapping_path in mapping_candidates:
        try:
            with mapping_path.open('r', encoding='utf-8-sig', newline='') as f:
                rows = list(csv.reader(f))
            mapping_count = max(0, len(rows) - 1)

            if article_count != mapping_count:
                print(
                    f"  AUDIT  BANK STRUCTURE MISMATCH: {html_path.name} has "
                    f"{article_count} real bank-item article(s), but "
                    f"{mapping_path.name} has {mapping_count} mapping row(s)."
                )
                audit_count += 1
        except Exception as exc:
            print(f"  AUDIT  Could not compare {mapping_path.name}: {exc}")
            audit_count += 1

print(f"\nDone. {fixed_count} file(s) auto-fixed. {audit_count} file(s) have audit warnings.")
