#!/usr/bin/env python3
# Universal Bank Finalizer v6 SAFE — embeds authoritative MathJax v9 repair engine
# Mechanical repair only; concise computer checks + targeted teacher review.
from pathlib import Path
from collections import defaultdict
import argparse, csv, html, json, re, shutil, subprocess, sys, zipfile

# --- EMBEDDED AUTHORITATIVE MATHJAX v9 REPAIR/AUDIT ENGINE ---
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
# V6 — MALFORMED DOLLAR / ESCAPED-HTML REPAIRS
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

# V8 — BARE CURRENCY / ESCAPED-COMMENT PROTECTION
#
# A prose currency token such as "$18 to start" can accidentally open a MathJax
# span that swallows following HTML. Repair only high-confidence currency uses
# in HTML text nodes BEFORE math-span parsing. Numeric math such as
# "$18+7c=53$" is left untouched because the amount is followed by an operator.
#
# Escaped HTML comments are also restored. A prior algebra cleanup can turn the
# closing "--" into "+" after a malformed math span, so both forms are accepted.

HTML_TOKEN_RE = re.compile(
    r'(<script\b.*?</script>|<style\b.*?</style>|<[^>]+>)',
    re.IGNORECASE | re.DOTALL,
)

CURRENCY_AMOUNT_RE = re.compile(
    r'(?<!\\)\$(?P<amount>\d+(?:,\d{3})*(?:\.\d{1,2})?)'
)

CURRENCY_CUE_RE = re.compile(
    r'\b(?:costs?|costing|price|fee|fees|charge|charges|pay|paid|pays|payment|'
    r'budget|spend|spends|spent|total|totals|dollars?|cents?|per|each|'
    r'membership|registration|admission|ticket|tickets|purchase|purchases)\b',
    re.IGNORECASE,
)

CURRENCY_POST_RE = re.compile(
    r'^\s+(?:to\s+start|to\s+begin|per\b|each\b|for\b|in\b|at\b|'
    r'dollars?\b|cents?\b|total\b|more\b|less\b)',
    re.IGNORECASE,
)

ESCAPED_HTML_COMMENT_RE = re.compile(
    r'\\lt\s*!--\s*([^\n]*?)\s*(?:--|\+)\\gt',
    re.IGNORECASE,
)


def _repair_currency_segment(segment):
    hits = 0

    def repl(match):
        nonlocal hits
        end = match.end()
        after = segment[end:end + 40]
        before = segment[max(0, match.start() - 45):match.start()]

        # A closing dollar, mathematical operator, opening delimiter, TeX command,
        # or coefficient-variable continuation immediately after the amount strongly
        # indicates a real MathJax expression, not currency. V8 explicitly protects
        # compact coefficient-leading math such as $4x+4=30$, $12n-5$, and $2t^2$.
        # V7 could misclassify these as currency when nearby prose contained words
        # such as "dollars" or "total", which could unbalance MathJax and swallow
        # following HTML structure.
        immediate = segment[end:end + 1]
        nearby_closing = '$' in segment[end:end + 120]
        if immediate == '$' or immediate in '+-*/=^_\\([':
            return match.group(0)
        if immediate and immediate.isalpha() and nearby_closing:
            return match.group(0)

        # High-confidence prose/currency context only.
        punctuation_prose = bool(re.match(r'^[,;:!?](?=\s|$)', after))
        period_prose = bool(re.match(r'^\.(?=\s|$)', after))
        cue = bool(CURRENCY_CUE_RE.search(before) or CURRENCY_POST_RE.search(after))

        # "$18 fixed dollars", "$5 fee", "$7 per class", etc. are
        # high-confidence currency. A rare math form such as "$2 x$" is
        # protected when the next token is a single-letter variable and a
        # closing dollar occurs shortly afterward.
        whitespace_prose = False
        if immediate.isspace():
            word_match = re.match(r'^\s+([A-Za-z]+)', after)
            next_word = word_match.group(1) if word_match else ''
            short_tail = after[:16]
            looks_like_short_math = (
                len(next_word) == 1
                and '$' in short_tail
                and not CURRENCY_CUE_RE.search(short_tail)
            )
            whitespace_prose = not looks_like_short_math

        if not (cue or punctuation_prose or period_prose or whitespace_prose):
            return match.group(0)

        hits += 1
        return r'\$' + match.group('amount')

    return CURRENCY_AMOUNT_RE.sub(repl, segment), hits


def repair_obvious_currency_html(text):
    """Escape high-confidence prose currency in HTML before MathJax parsing."""
    parts = HTML_TOKEN_RE.split(text)
    out = []
    hits = 0
    for part in parts:
        if not part:
            continue
        if HTML_TOKEN_RE.fullmatch(part):
            out.append(part)
            continue
        repaired, n = _repair_currency_segment(part)
        out.append(repaired)
        hits += n
    return ''.join(out), hits


def repair_escaped_html_comments(text):
    r"""Restore escaped HTML comments, including +\gt closings from -- cleanup."""
    hits = 0

    def repl(match):
        nonlocal hits
        hits += 1
        content = match.group(1).strip()
        return f"<!--{content}-->"

    return ESCAPED_HTML_COMMENT_RE.sub(repl, text), hits


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

# V9 — production repair for a corrupted \\left / \\right command that can
# surface as the Unicode relation fragments ‘≤ft’ / ‘≥ight’ inside math.
# Restrict repair to math blocks and delimiter-following positions.
LEFT_GLYPH_TAIL_RE = re.compile(r'(?:≤|&le;|&#8804;)\s*ft(?=\s*[({\[])')
RIGHT_GLYPH_TAIL_RE = re.compile(r'(?:≥|&ge;|&#8805;)\s*ight(?=\s*[)}\]])')


# V6: Python string escapes can become literal control characters before a
# generated HTML file is written. Byte-level repairs catch most cases, but
# \to followed immediately by a value (for example "$1\to4$") was previously
# missed and then degraded into "\qquad o4".
#
# These repairs run INSIDE math before generic tab cleanup.
TAB_TEX_TAIL_FIXES = [
    (re.compile(r'\theta'), r'\\theta'),
    (re.compile(r'\text\{'), r'\\text{'),
    (re.compile(r'\times'), r'\\times'),
    (re.compile(r'\to(?=[0-9A-Za-z({\[+\-])'), r'\\to '),
]

# A carriage-return escape such as "\rightarrow" may be normalized by a
# text read/write pass into a real newline followed by "ightarrow". Repair
# only inside a MathJax block, where these command tails are unambiguous.
NEWLINE_TEX_TAIL_FIXES = [
    (re.compile(r'\r?\nightarrow'), r'\\rightarrow'),
    (re.compile(r'\r?\nangle'), r'\\rangle'),
]


# A TeX relation command followed immediately by a LETTER variable is parsed as
# one unknown command. Production example:
#     \ltx   -> intended \lt x
#
# Conservative safeguards:
#   • only common relation commands are repaired
#   • q is excluded as the following variable so valid \leq / \geq / \neq
#     commands are never rewritten
#   • the variable must be followed by a normal mathematical boundary
#
# Examples repaired:
#   \ltx -> \lt x
#   \gty -> \gt y
#   \lex -> \le x
#   \gex -> \ge x
#   \nex -> \ne x
MERGED_RELATION_RE = re.compile(
    r'\\(?P<rel>lt|gt|le|ge|ne)'
    r'(?P<var>[a-pr-zA-PR-Z])'
    r'(?=(?:\^|_|[+\-*/=<>),.;:\]}]|\\|$|\s))'
)


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
    r'(<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>)',
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
      • merged relation commands:     \ltx -> \lt x

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
        'merged_relation': 0,
        'tab_tex_tail': 0,
        'newline_tex_tail': 0,
        'left_glyph_tail': 0,
        'right_glyph_tail': 0,
    }

    def repl(match):
        whole = match.group(0)
        delim = '$$' if whole.startswith('$$') else '$'
        content = whole[len(delim):-len(delim)]

        # V9) Restore corrupted \\left / \\right glyph tails seen in production.
        n = len(LEFT_GLYPH_TAIL_RE.findall(content))
        if n:
            content = LEFT_GLYPH_TAIL_RE.sub(r'\\left', content)
            counts['left_glyph_tail'] += n
        n = len(RIGHT_GLYPH_TAIL_RE.findall(content))
        if n:
            content = RIGHT_GLYPH_TAIL_RE.sub(r'\\right', content)
            counts['right_glyph_tail'] += n

        # 1) Restore TeX commands whose leading backslash became a tab.
        for pattern, replacement in TAB_TEX_TAIL_FIXES:
            n = len(pattern.findall(content))
            if n:
                content = pattern.sub(replacement, content)
                counts['tab_tex_tail'] += n

        # 2) Restore TeX commands whose \r escape was normalized to a newline.
        for pattern, replacement in NEWLINE_TEX_TAIL_FIXES:
            n = len(pattern.findall(content))
            if n:
                content = pattern.sub(replacement, content)
                counts['newline_tex_tail'] += n

        # 3) Any OTHER literal tab inside math is formatting corruption.
        #    Preserve the old conservative fallback only after command repair.
        tab_count = content.count('\t')
        if tab_count:
            content = content.replace('\t', r'\qquad ')
            counts['tabs'] += tab_count

        # 4) Collapse two literal backslashes before an alphabetic TeX command.
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

        # 6) Repair relation commands accidentally merged with a letter variable.
        #    Example: \ltx -> \lt x
        def relation_repl(match):
            counts['merged_relation'] += 1
            return '\\' + match.group('rel') + ' ' + match.group('var')

        content = MERGED_RELATION_RE.sub(relation_repl, content)

        # 7) Raw < and > are unsafe in HTML source inside math. Convert them.
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
    if counts['merged_relation']:
        hits.append(
            f"         {counts['merged_relation']}× merged relation command separated "
            "(for example \\ltx→\\lt x)"
        )
    if counts['tab_tex_tail']:
        hits.append(
            f"         {counts['tab_tex_tail']}× tab-corrupted TeX command restored "
            "(for example tab+o4→\\to 4 or tab+imes→\\times)"
        )
    if counts['newline_tex_tail']:
        hits.append(
            f"         {counts['newline_tex_tail']}× newline-corrupted TeX command restored "
            "(for example newline+ightarrow→\\rightarrow)"
        )

    if counts['left_glyph_tail']:
        hits.append(
            f"         {counts['left_glyph_tail']}× corrupted ≤ft delimiter command restored to \\left"
        )
    if counts['right_glyph_tail']:
        hits.append(
            f"         {counts['right_glyph_tail']}× corrupted ≥ight delimiter command restored to \\right"
        )

    return new_text, hits


def repair_tarsia_delimiters(text):
    r"""
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

    escaped_comments = len(ESCAPED_HTML_COMMENT_RE.findall(text))
    if escaped_comments:
        warnings.append(
            f"    ESCAPED HTML COMMENT: {escaped_comments} comment(s) remain as \\lt !-- ... \\gt"
        )

    # Presentation HTML inside math should have been stripped.
    inline_tag_math = 0
    for block in math_blocks:
        inline_tag_math += len(INLINE_PRESENTATION_TAG_RE.findall(block))
    if inline_tag_math:
        warnings.append(
            f"    HTML INSIDE MATH: {inline_tag_math} presentation tag(s) remain inside MathJax blocks"
        )

    # Bare dropped fraction command should be gone after V6 repair.
    bare_rac = 0
    for block in math_blocks:
        bare_rac += len(BARE_RAC_RE.findall(block))
    if bare_rac:
        warnings.append(
            f"    DROPPED FRAC COMMAND: {bare_rac} bare rac{{...}} instance(s) remain inside math"
        )

    # Merged relation commands such as \\ltx should be gone after V6 repair.
    merged_rel = 0
    for block in math_blocks:
        merged_rel += len(MERGED_RELATION_RE.findall(block))
    if merged_rel:
        warnings.append(
            f"    MERGED RELATION COMMAND: {merged_rel} instance(s) remain "
            "(for example \\ltx, \\lex, or \\nex)"
        )

    # V9: corrupted left/right glyph tails should be gone after repair.
    left_glyph_left = sum(len(LEFT_GLYPH_TAIL_RE.findall(b)) for b in math_blocks)
    right_glyph_left = sum(len(RIGHT_GLYPH_TAIL_RE.findall(b)) for b in math_blocks)
    if left_glyph_left:
        warnings.append(
            f"    CORRUPTED LEFT COMMAND: {left_glyph_left} instance(s) of ≤ft remain inside math"
        )
    if right_glyph_left:
        warnings.append(
            f"    CORRUPTED RIGHT COMMAND: {right_glyph_left} instance(s) of ≥ight remain inside math"
        )

    # V6: command-tail corruption should be gone after repair.
    remaining_tab_tails = 0
    remaining_newline_tails = 0
    for block in math_blocks:
        for pattern, _ in TAB_TEX_TAIL_FIXES:
            remaining_tab_tails += len(pattern.findall(block))
        for pattern, _ in NEWLINE_TEX_TAIL_FIXES:
            remaining_newline_tails += len(pattern.findall(block))

    if remaining_tab_tails:
        warnings.append(
            f"    TAB-CORRUPTED TEX COMMAND: {remaining_tab_tails} instance(s) remain inside math"
        )
    if remaining_newline_tails:
        warnings.append(
            f"    NEWLINE-CORRUPTED TEX COMMAND: {remaining_newline_tails} instance(s) remain inside math"
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
# --- END EMBEDDED MATHJAX v9 ENGINE ---

CANONICAL_BANK_CSS = '''/* Universal Bank - canonical clean teacher inspection style.
   Production location: css/bank.css
   Load AFTER css/base.css. */
body {
  font-family: Arial, sans-serif;
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
  color: #1d2433;
  background: #fff;
}
h1, h2, h3 { color: #1f3864; }
.nav {
  position: sticky; top: 0; z-index: 4; display: flex; flex-wrap: wrap; column-gap: 20px; row-gap: 8px;
  background: #fff; padding: 10px; margin: 12px 0 20px; border-bottom: 1px solid #ccc;
}
.nav a { display: inline-block; color: #1f3864; text-decoration: none; white-space: nowrap; }
.nav a:hover { text-decoration: underline; }
.bank-section { margin: 0 0 30px; }
.resource-group { margin: 0; padding: 0; }
.resource-group > h3 { margin-top: 24px; margin-bottom: 8px; }
.bank-item { border: 1px solid #d7dce5; border-radius: 8px; padding: 14px; margin: 12px 0; background: #fff; }
.meta { margin-bottom: 8px; font-size: 12px; color: #596579; }
.student-prompt { margin: 0; }
.student-prompt > :first-child { margin-top: 0; }
.student-prompt > :last-child { margin-bottom: 0; }
.answer { margin-top: 8px; background: #f1f6f1; border-left: 4px solid #437a43; padding: 8px; }
.answer > summary, .evidence-map > summary { cursor: pointer; font-weight: bold; }
.answer[open] > summary, .evidence-map[open] > summary { margin-bottom: 6px; }
.evidence-map { display: block; margin: 8px 0 0; padding: 7px 9px; font-size: 12px; line-height: 1.45; color: #596579; border-left: 3px solid #d7dce5; background: #fafbfc; }
img { max-width: 560px; max-height: 380px; display: block; margin: 10px auto; }
figure { margin: 10px 0; }
figcaption { margin-top: 4px; text-align: center; font-size: 12px; color: #596579; }
table { border-collapse: collapse; margin: 10px 0; }
td, th { border: 1px solid #999; padding: 5px 9px; }
.secure, .bank-item.secure, [data-security="summative-secure"] { border-color: #8b5a2b; }
section[id] { scroll-margin-top: 72px; }
@media (max-width: 720px) { body { padding: 14px; } .nav { column-gap: 14px; } img { max-width: 100%; height: auto; } }
'''
CANONICAL_MATHJAX = '''<script>
window.MathJax = {
  tex: {
    inlineMath: [['$','$']],
    displayMath: [['$$','$$']],
    processEscapes: true
  }
};
</script>'''
REQUIRED_SUFFIXES=['_bank_data.json','_downstream_manifest.json','_i_can_map.csv','_mapping.csv','_evidence_map.csv','_summative_source_map.csv']
JUNK_NAMES={'.DS_Store'}
TAG_RE=re.compile(r'<[^>]+>')
WS_RE=re.compile(r'\s+')
SCRIPT_STYLE_RE=re.compile(r'<(?:script|style)\b.*?</(?:script|style)>',re.I|re.S)
MATHJAX_CONFIG_RE=re.compile(r'<script>\s*window\.MathJax\s*=.*?</script>',re.I|re.S)
PLACEHOLDER_RE=re.compile(r'\b(?:TODO|TBD|PLACEHOLDER|FIXME)\b|\{\{[^}]+\}\}|\{html\.escape\(',re.I)
def clean_text(v):
    if v is None:return ''
    return WS_RE.sub(' ',html.unescape(TAG_RE.sub(' ',str(v)))).strip()

def normalize_prompt(v):return clean_text(v).lower().strip()

def skeleton_prompt(v):
    s=normalize_prompt(v);s=re.sub(r'(?<![a-z])[-+]?\d+(?:\.\d+)?(?:/\d+)?','#',s)
    s=re.sub(r'\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b','#',s)
    return WS_RE.sub(' ',s).strip()

def run(cmd,cwd=None):
    p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    return p.returncode,p.stdout

def resolve_bank_dir(source=None):
    if source:
        p=Path(source).expanduser().resolve()
        if not p.exists():raise RuntimeError(f'Source does not exist: {p}')
        if p.is_file():raise RuntimeError('Pass an extracted unitN/ folder, not a ZIP file.')
        if re.fullmatch(r'unit\d+',p.name,re.I):return p
        c=[x for x in p.iterdir() if x.is_dir() and re.fullmatch(r'unit\d+',x.name,re.I)]
        if len(c)==1:return c[0]
        raise RuntimeError('Could not resolve exactly one unitN/ folder from source.')
    here=Path(__file__).resolve().parent
    if re.fullmatch(r'unit\d+',here.name,re.I):return here
    c=[x for x in here.iterdir() if x.is_dir() and re.fullmatch(r'unit\d+',x.name,re.I)]
    if len(c)==1:return c[0]
    raise RuntimeError('Put ~finalize_bank.py inside the extracted unitN/ folder, or pass that folder as an optional argument.')

def remove_junk(root):
    n=0
    for p in sorted(root.rglob('*'),key=lambda x:len(x.parts),reverse=True):
        if '__MACOSX' in p.parts or p.name in JUNK_NAMES or p.name.startswith('._'):
            try: shutil.rmtree(p) if p.is_dir() else p.unlink(); n+=1
            except Exception:pass
    return n

def sync_shared_css(base):
    try:
        p=base.parent.parent/'css'/'bank.css'
        if p.exists() and p.read_text(encoding='utf-8',errors='replace')!=CANONICAL_BANK_CSS:
            p.write_text(CANONICAL_BANK_CSS,encoding='utf-8');return True
    except Exception:pass
    return False

def _normalize_mathjax_head_and_nav(text):
    # Locked dollar-delimited MathJax config before CDN + visible nav whitespace.
    if 'window.MathJax' in text:
        text=MATHJAX_CONFIG_RE.sub(CANONICAL_MATHJAX,text,count=1)
    elif 'cdn.jsdelivr.net/npm/mathjax' in text:
        text=text.replace('<script async src="https://cdn.jsdelivr.net/npm/mathjax',CANONICAL_MATHJAX+'\n<script async src="https://cdn.jsdelivr.net/npm/mathjax',1)
    text=re.sub(r'</a>\s*<a\b','</a>\n    <a',text)
    return text

SIMPLE_OUTSIDE_RELATION_RE=re.compile(
    r'(?<![$\\])(?P<left>(?:[-+]?\d+(?:\.\d+)?\s*)?[A-Za-z](?:\s*[+-]\s*\d+(?:\.\d+)?)?|[-+]?\d+(?:\.\d+)?)'
    r'\s*\\(?P<rel>gt|lt|le|ge|ne)\s*'
    r'(?P<right>[-+]?\d+(?:\.\d+)?|(?:[-+]?\d+(?:\.\d+)?\s*)?[A-Za-z])'
)

def _repair_simple_outside_relations_html(text):
    # High-confidence authoring leak: visible algebra such as -3x \\gt -6 or x \\lt 2.
    # IMPORTANT: operate ONLY outside existing $...$ / $$...$$ spans. A prior version
    # could wrap a relation already inside math, creating nested dollar delimiters that
    # swallowed later HTML during MathJax repair.
    parts=PROTECTED_HTML_RE.split(text)
    out=[]; hits=0
    def repl(m):
        nonlocal hits
        hits+=1
        rel={'gt':'>','lt':'<','le':r'\\le','ge':r'\\ge','ne':r'\\ne'}[m.group('rel')]
        return f"${m.group('left').strip()} {rel} {m.group('right').strip()}$"
    for part in parts:
        if PROTECTED_HTML_RE.fullmatch(part or ''):
            out.append(part);continue
        tokens=HTML_TOKEN_RE.split(part)
        for tok in tokens:
            if not tok:continue
            if HTML_TOKEN_RE.fullmatch(tok):
                out.append(tok);continue
            pos=0
            for mm in MATH_BLOCK_RE.finditer(tok):
                outside=tok[pos:mm.start()]
                out.append(SIMPLE_OUTSIDE_RELATION_RE.sub(repl,outside))
                out.append(mm.group(0))
                pos=mm.end()
            out.append(SIMPLE_OUTSIDE_RELATION_RE.sub(repl,tok[pos:]))
    return ''.join(out),hits

OUTSIDE_TEX_RE=re.compile(r'\\(?:gt|lt|le|ge|ne|frac|sqrt|times|theta|rightarrow|to|text|begin|end)\b')

def _outside_math_tex_warnings(path,text):
    # After v9 repair, raw TeX command words visible OUTSIDE $...$ are suspicious.
    if path.suffix.lower()!='.html':
        return []
    body=SCRIPT_STYLE_RE.sub('',text)
    body=MATH_BLOCK_RE.sub(' ',body)
    visible=html.unescape(TAG_RE.sub(' ',body))
    hits=OUTSIDE_TEX_RE.findall(visible)
    if not hits:
        return []
    sample=', '.join(sorted(set(hits))[:6])
    return [f'RAW TEX OUTSIDE MATH: {len(hits)} command(s) remain visible outside math delimiters ({sample})']

def _repair_serialized_comparisons_safe(text):
    # v9 base's whole-document regex can backtrack heavily on large Bank HTML.
    # Apply the same repair line-by-line only where the signature could exist.
    out=[]; hits=0
    for line in text.splitlines(keepends=True):
        if '$' in line and '<' in line and '</' in line and len(line)<=20000:
            line,n=repair_serialized_comparisons(line); hits+=n
        out.append(line)
    return ''.join(out),hits

def _fast_residual_math_audit(path,text):
    warnings=[]
    math_blocks=[m.group(0) for m in MATH_BLOCK_RE.finditer(text)]
    if any(any(ord(ch) in {7,8,11,12} for ch in block) for block in math_blocks):
        warnings.append('CONTROL-BYTE TEX CORRUPTION remains inside math')
    if any('<' in b or '>' in b for b in math_blocks):
        warnings.append('RAW < or > remains inside math')
    if any(re.search(r'\\\\(?=[A-Za-z])',b) for b in math_blocks):
        warnings.append('DOUBLED TEX ESCAPE remains inside math')
    if any(BARE_RAC_RE.search(b) for b in math_blocks):
        warnings.append('DROPPED FRAC COMMAND remains inside math')
    if any(MERGED_RELATION_RE.search(b) for b in math_blocks):
        warnings.append('MERGED RELATION COMMAND remains inside math')
    if any(LEFT_GLYPH_TAIL_RE.search(b) for b in math_blocks):
        warnings.append('CORRUPTED LEFT COMMAND (≤ft) remains inside math')
    if any(RIGHT_GLYPH_TAIL_RE.search(b) for b in math_blocks):
        warnings.append('CORRUPTED RIGHT COMMAND (≥ight) remains inside math')
    if NESTED_INLINE_ASSIGNMENT_RE.search(text):
        warnings.append('MALFORMED NESTED MATH remains')
    if path.suffix.lower()=='.html':
        if ESCAPED_HTML_TAG_RE.search(text):warnings.append('ESCAPED HTML STRUCTURE remains')
        if ESCAPED_HTML_COMMENT_RE.search(text):warnings.append('ESCAPED HTML COMMENT remains')
        for b in math_blocks:
            if INLINE_PRESENTATION_TAG_RE.search(b):
                warnings.append('HTML PRESENTATION TAG remains inside math');break
        no_scripts=SCRIPT_STYLE_RE.sub('',text)
        outside=MATH_BLOCK_RE.sub(' ',no_scripts)
        if re.search(r'(?<!\\)(?<!\$)\$(?!\$)\d',outside):
            warnings.append('BARE CURRENCY-LIKE $[digit] remains outside math')
        if 'mathjax' in text.lower() and ('cdnjs' in text or 'unpkg' in text):
            warnings.append('WRONG MATHJAX CDN remains')
        config_pos=text.find('window.MathJax');cdn_pos=text.find('cdn.jsdelivr.net')
        if config_pos!=-1 and cdn_pos!=-1 and config_pos>cdn_pos:
            warnings.append('MATHJAX CONFIG appears after CDN')
    if path.suffix.lower() in {'.txt','.csv'}:
        bad=[]
        for n,line in enumerate(text.splitlines(),1):
            if len(re.findall(r'(?<!\\)\$',line))%2:bad.append(n)
        if bad:warnings.append('UNBALANCED $ DELIMITERS on line(s) '+', '.join(map(str,bad[:8])))
    return warnings

def safe_repair_files(base):
    """Apply authoritative v9 repairs silently; return only unresolved audit warnings."""
    changed=0
    residual=[]
    for p in base.rglob('*'):
        if (not p.is_file() or p.suffix.lower() not in {'.html','.txt','.csv','.json'}
                or '__MACOSX' in p.parts or p.name.startswith('._')):
            continue
        raw=p.read_bytes(); new_raw=raw
        # v9 Section 1 — byte-level fixes
        for corrupt,replacement,_label in FIXES:
            if corrupt in new_raw:
                new_raw=new_raw.replace(corrupt,replacement)
        # v9 Section 2 — wrong delimiter repairs
        for pattern,replacement,_label in REGEX_FIXES:
            new_raw=pattern.sub(replacement,new_raw)
        text=new_raw.decode('utf-8',errors='replace')
        original_text=text
        suffix=p.suffix.lower()
        tex_export_mode=False
        if suffix=='.html':
            # V9 high-confidence preparse repair: fix the exact corrupted command
            # tails BEFORE any math/HTML parsing can swallow surrounding markup.
            text=text.replace('≤ft', r'\left').replace('≥ight', r'\right')
        if suffix=='.json':
            # JSON stores TeX backslashes escaped. Only apply the narrow v9 glyph-tail
            # repair here; generic slash/delimiter normalization would corrupt JSON.
            text=re.sub(r'(?:≤|&le;|&#8804;)\s*ft(?=\s*[({\[])', r'\\\\left', text)
            text=re.sub(r'(?:≥|&ge;|&#8805;)\s*ight(?=\s*[)}\]])', r'\\\\right', text)
            if text!=original_text or new_raw!=raw:
                p.write_text(text,encoding='utf-8');changed+=1
            try:
                json.loads(text)
            except Exception as exc:
                residual.append({'file':str(p.relative_to(base)),'warning':f'INVALID JSON after safe repair: {exc}'})
            continue
        if suffix=='.html':
            text=_normalize_mathjax_head_and_nav(text)
            text,_=repair_obvious_currency_html(text)
            text,_=repair_malformed_math_assignments(text)
            text,_=repair_escaped_html_tags(text)
            text,_=repair_escaped_html_comments(text)
            text,_=_repair_serialized_comparisons_safe(text)
            text,_=_repair_simple_outside_relations_html(text)
            text,_=repair_math_blocks(text)
            text,_=repair_algebra_notation(text,is_html=True)
        elif suffix=='.txt':
            # Plain Tarsia/text exports often use literal currency $ and plain equations.
            # Only interpret dollar signs as MathJax when the export actually contains TeX commands.
            tex_export_mode=bool(re.search(r'\\(?:frac|lim|to|sqrt|theta|times|lt|gt|le|ge|neq|infty)\b|\$\$',text))
            if tex_export_mode:
                text,_=repair_malformed_math_assignments(text)
                text,_=repair_math_blocks(text)
                if p.name.startswith('tarsia_'):
                    text,_=repair_tarsia_delimiters(text)
        # CSV/Blooket is plain import text: do not reinterpret literal dollar signs as MathJax.
        if text!=original_text or new_raw!=raw:
            p.write_text(text,encoding='utf-8')
            changed+=1
        final=p.read_text(encoding='utf-8',errors='replace')
        warnings=[]
        if suffix=='.html' or tex_export_mode:
            warnings=_fast_residual_math_audit(p,final)
        if suffix=='.html':
            warnings.extend(_outside_math_tex_warnings(p,final))
        for w in warnings:
            residual.append({'file':str(p.relative_to(base)),'warning':w})
    return changed,residual

INTERNAL_LABEL_RE=re.compile(r'^\s*(?:Example anchor|YTI anchor|You Try It anchor|Evidence task|Architecture|Structure ID)\s*:',re.I)
LARGE_LINEAR_PARAM_RE=re.compile(r'\by\s*=\s*[-+]?\d*(?:\.\d+)?\s*x\s*([+-])\s*(\d{3,})\b',re.I)
CONTEXT_LARGE_VALUE_RE=re.compile(r'\b(?:population|revenue|salary|dollars?|cost|price|money|budget|miles?|kilometers?|meters?|people|students|year|temperature|mass|force|energy|data)\b',re.I)

def suspicious_large_algebra_parameter(text):
    plain=clean_text(text)
    m=LARGE_LINEAR_PARAM_RE.search(plain)
    if not m:return False
    if CONTEXT_LARGE_VALUE_RE.search(plain):return False
    return int(m.group(2))>=100

def _summative_skeleton_sequences(versions):
    out={}
    for v,vals in versions.items():
        out[v]=[skeleton_prompt(clean_text(x.get('student_text') or x.get('student_html'))) for x in vals]
    return out

def _sequence_overlap(a,b):
    if not a or not b:return 0.0
    from collections import Counter
    ca,cb=Counter(a),Counter(b)
    shared=sum((ca & cb).values())
    return shared/max(len(a),len(b))

def possible_unrelated_multipart(text):
    # Deliberately HIGH-CONFIDENCE only. Generic and/then/two-verb logic produced
    # false positives on coherent WTCs, solve+graph, and explain-your-result tasks.
    low=normalize_prompt(text)
    return ('diamond' in low and any(k in low for k in (
        'plot ', 'coordinate plane', 'write an equation', 'write a rule',
        'complete the table', 'make a table', 'graph the point', 'graph the line'
    )))

PRACTICE_ITERATION_LABEL_RE=re.compile(
    r'\b(?:on this second pass|second pass|another version|repeat(?:ed)? version|'
    r'make the verification step explicit)\b', re.I
)
GENERIC_WRAPPER_CUE_RE=re.compile(
    r'\b(?:show|check|explain|include|state|verify|verification|reason|reasonable|'
    r'representation|setup|work|sentence|before stating|after solving)\b', re.I
)

def _practice_trailing_sentence(text):
    plain=clean_text(text).strip()
    if not plain:return ''
    parts=[x.strip() for x in re.split(r'(?<=[.!?])\s+',plain) if x.strip()]
    if not parts:return ''
    tail=parts[-1]
    if len(tail)<45 or len(tail)>240:return ''
    if not GENERIC_WRAPPER_CUE_RE.search(tail):return ''
    return tail

def detect_course_family(data):
    raw=str(data.get('course_family') or '').strip().lower().replace('-','_').replace(' ','_')
    aliases={'spiral':'spiral_math','spiral_math':'spiral_math','ap_calc':'ap_calculus','ap_calculus':'ap_calculus','science':'science','physics':'science','chemistry':'science','biology':'science'}
    if raw in aliases:return aliases[raw]
    course=str(data.get('course') or '').lower()
    if 'calculus' in course and ('ap' in course or 'advanced placement' in course):return 'ap_calculus'
    if any(x in course for x in ('physics','chemistry','biology','science')):return 'science'
    if any(x in course for x in ('algebra','geometry','precalculus','math')):return 'spiral_math'
    return 'other'

def is_selected(item):
    typ=clean_text(item.get('item_type')).lower();choices=item.get('choices') or []
    return bool(choices) or any(k in typ for k in ('multiple choice','multiple-choice','selected response','selected-response'))

def checks(base,residual_math):
    hard=[];review=[];counts={};ck={}
    m=re.fullmatch(r'unit(\d+)',base.name,re.I);unit=m.group(1) if m else '?'
    req=[base/f'unit{unit}.html',base/'generate_graphs.py',base/'~finalize_bank.py']+[base/f'unit{unit}{s}' for s in REQUIRED_SUFFIXES]
    miss=[p.name for p in req if not p.exists()];ck['required_files']='PASS' if not miss else 'FAIL'
    for x in miss:hard.append({'where':'PACKAGE','issue':f'Missing required file: {x}'})
    if miss:counts['checks']=ck;return hard,review,counts
    try:data=json.loads((base/f'unit{unit}_bank_data.json').read_text(encoding='utf-8'));items=data.get('items',[])
    except Exception as e:return [{'where':'PACKAGE','issue':f'Cannot parse bank_data JSON: {e}'}],review,{'checks':{'required_files':'PASS','canonical_data':'FAIL'}}
    family=detect_course_family(data);counts['course_family']=family;counts['canonical_items']=len(items)
    try:
        with (base/f'unit{unit}_mapping.csv').open(encoding='utf-8-sig',newline='') as f:mapping=list(csv.DictReader(f))
    except Exception as e:mapping=[];hard.append({'where':'PACKAGE','issue':f'Cannot parse mapping CSV: {e}'})
    counts['mapping_rows']=len(mapping);htmlp=base/f'unit{unit}.html';ht=htmlp.read_text(encoding='utf-8',errors='replace')
    articles=len(re.findall(r'<article\b[^>]*class=["\'][^"\']*\bbank-item\b[^>]*>',ht,re.I));counts['html_bank_items']=articles
    if articles==len(mapping)==len(items):ck['html_mapping_json']=f'PASS ({articles})'
    else:ck['html_mapping_json']='FAIL';hard.append({'where':'PACKAGE','issue':f'Canonical counts disagree: HTML={articles}, mapping={len(mapping)}, JSON={len(items)}'})
    mathok="inlineMath: [['$','$']]" in ht and "displayMath: [['$$','$$']]" in ht
    body=SCRIPT_STYLE_RE.sub('',ht);balanced=len(re.findall(r'(?<!\\)\$',body))%2==0
    if not mathok:hard.append({'where':'HTML','issue':'MathJax head is not configured for $...$ / $$...$$.'})
    if not balanced:hard.append({'where':'HTML','issue':'Unbalanced unescaped $ delimiters remain in Bank HTML.'})
    if residual_math:
        for r in residual_math[:30]:
            review.append({'where':f"MATHJAX {r.get('file','?')}",'issue':r.get('warning','Residual MathJax/HTML warning')})
        if len(residual_math)>30:
            review.append({'where':'MATHJAX','issue':f'{len(residual_math)-30} additional residual warning(s) are in the machine report.'})
    ck['mathjax_html']='PASS' if mathok and balanced and not residual_math else ('REVIEW' if mathok and balanced else 'FAIL')
    ids=set();exact=defaultdict(list);practice_tails=defaultdict(list);practice_iteration=[]
    for item in items:
        bid=str(item.get('bank_id') or '<missing-id>')
        if bid in ids:hard.append({'where':bid,'issue':'Duplicate bank_id'})
        ids.add(bid);prompt=clean_text(item.get('student_text') or item.get('student_html'))
        if not prompt:hard.append({'where':bid,'issue':'Blank student prompt'});continue
        if PLACEHOLDER_RE.search(prompt):hard.append({'where':bid,'issue':'Unresolved placeholder/template text'})
        if INTERNAL_LABEL_RE.search(prompt):review.append({'where':bid,'issue':'Internal authoring label leaked into the student-facing prompt (for example Example anchor:/YTI anchor:).'})
        if family=='spiral_math' and suspicious_large_algebra_parameter(prompt):review.append({'where':bid,'issue':'Suspiciously large direct-Algebra linear parameter with no obvious context reason. Check whether the value is pedagogically natural/graph-friendly.'})
        if family in ('spiral_math','ap_calculus') and is_selected(item):hard.append({'where':bid,'issue':f'Multiple-choice/selected-response is not allowed for {family} canonical Bank/Summative items. Blooket is the exception.'})
        dest=clean_text(item.get('destination') or item.get('destination_group')).lower()
        if 'practice' in dest:
            if PRACTICE_ITERATION_LABEL_RE.search(prompt):practice_iteration.append(bid)
            tail=_practice_trailing_sentence(prompt)
            if tail:practice_tails[normalize_prompt(tail)].append((bid,tail))
        for fig in item.get('figures') or []:
            f=fig.get('file') if isinstance(fig,dict) else str(fig)
            if f and not (base/f).exists():hard.append({'where':bid,'issue':f'Missing referenced figure: {f}'})
        exact[normalize_prompt(prompt)].append(bid)
        if possible_unrelated_multipart(prompt):review.append({'where':bid,'issue':'High-confidence unrelated bundle: a Diamond Problem appears glued to an independent coordinate/equation/table task.'})
    dups=[b for p,b in exact.items() if p and len(b)>1];counts['exact_duplicate_groups']=len(dups)
    for bids in dups[:30]:review.append({'where':', '.join(bids[:8]),'issue':f'Exact student prompt duplicated across {len(bids)} canonical items.'})
    if practice_iteration:
        review.append({'where':'PRACTICE','issue':f'{len(practice_iteration)} Practice item(s) expose iteration/generator language such as second pass/another version. Repeated problems should read as ordinary clean questions. First IDs: {", ".join(practice_iteration[:8])}'})
    wrapper_groups=[vals for vals in practice_tails.values() if len(vals)>=8]
    wrapper_groups.sort(key=len,reverse=True)
    for vals in wrapper_groups[:8]:
        sample=vals[0][1]
        review.append({'where':'PRACTICE','issue':f'Repeated generic trailing wrapper appears on {len(vals)} Practice questions: {sample[:180]!r}. Use item-specific explanation/checking only when that task benefits from it.'})
    counts['practice_stock_wrapper_groups']=len(wrapper_groups)
    by=defaultdict(lambda:defaultdict(int))
    for r in mapping:
        sec=str(r.get('section') or '').strip();dest=str(r.get('destination') or r.get('destination_group') or '').lower()
        if not sec:continue
        key=None
        if 'wtc' in dest or "what's to come" in dest:key='WTC'
        elif 'note' in dest and ('example' in dest or 'yti' in dest or 'you try' in dest):key='NOTES'
        elif 'practice' in dest and 'extra' in dest:key='EXTRA'
        elif 'practice' in dest and ('set 1' in dest or 'practice 1' in dest or 'ps1' in dest):key='P1'
        elif 'practice' in dest and ('set 2' in dest or 'practice 2' in dest or 'ps2' in dest):key='P2'
        elif 'practice' in dest and ('set 3' in dest or 'practice 3' in dest or 'ps3' in dest):key='P3'
        elif 'cyu' in dest:key='CYU'
        elif 'warm' in dest and ('1' in dest or 'wu1' in dest):key='WU1'
        elif 'warm' in dest and ('2' in dest or 'wu2' in dest):key='WU2'
        elif 'warm' in dest and ('3' in dest or 'wu3' in dest):key='WU3'
        elif 'exit' in dest and ('et-a' in dest or 'ticket a' in dest or 'ticket 1' in dest):key='ETA'
        elif 'exit' in dest and ('et-b' in dest or 'ticket b' in dest or 'ticket 2' in dest):key='ETB'
        elif 'exit' in dest and ('et-c' in dest or 'ticket c' in dest or 'ticket 3' in dest):key='ETC'
        if key:by[sec][key]+=1
    expected={'WTC':1,'NOTES':12,'P1':24,'P2':24,'P3':24,'EXTRA':24,'CYU':6,'WU1':4,'WU2':4,'WU3':4,'ETA':4,'ETB':4,'ETC':4};inv=True
    counts['sections']=len(by);counts['inventory_by_section']={s:dict(v) for s,v in sorted(by.items())}
    for sec,vals in sorted(by.items()):
        for key,n in expected.items():
            if vals.get(key,0)!=n:inv=False;hard.append({'where':f'Section {sec}','issue':f'Inventory {key}={vals.get(key,0)}, expected {n}.'})
    ck['locked_inventory']='PASS' if inv else 'FAIL'
    ex=base/'exports';tc={};bc={};eok=True
    if ex.exists():
        for f in sorted(ex.glob('tarsia_*_practice_3.txt')):
            n=len([x for x in f.read_text(encoding='utf-8-sig',errors='replace').splitlines() if x.strip()]);tc[f.name]=n
            if n!=18:eok=False;hard.append({'where':f.name,'issue':f'Tarsia active pairs={n}, expected 18.'})
        for f in sorted(ex.glob('blooket_*_practice_3.csv')):
            with f.open(encoding='utf-8-sig',newline='') as fh:rows=list(csv.reader(fh))
            active=[r for r in rows[1:] if r and str(r[0]).strip().isdigit() and len(r)>1 and str(r[1]).strip()];n=len(active);bc[f.name]=n
            if n!=20:eok=False;hard.append({'where':f.name,'issue':f'Blooket active questions={n}, expected 20.'})
    counts['tarsia']=tc;counts['blooket']=bc;counts['exports']=len([p for p in ex.glob('*') if p.is_file()]) if ex.exists() else 0;ck['exports']='PASS' if eok else 'FAIL'
    versions=defaultdict(list)
    for item in items:
        v=str(item.get('summative_version') or '').strip().upper()
        if v:versions[v].append(item)
    counts['summative_counts']={v:len(x) for v,x in sorted(versions.items())};sok=True
    if set(versions)!={'V1','V2','V3','V4','V5','V6'}:sok=False;hard.append({'where':'SUMMATIVE','issue':f'Versions present={sorted(versions)}, expected V1-V6.'})
    if family=='science':
        for v,vals in sorted(versions.items()):
            sr=sum(is_selected(x) for x in vals);cr=len(vals)-sr
            if len(vals)!=20 or sr!=16 or cr!=4:sok=False;hard.append({'where':f'SUMMATIVE {v}','issue':f'Science profile requires 20 items = 16 selected-response + 4 constructed-response; found total={len(vals)}, selected={sr}, constructed={cr}.'})
    # Security-form review: V1-V4 may share families, but should not all preserve the same family order.
    seqs=_summative_skeleton_sequences(versions)
    testday=[v for v in ('V1','V2','V3','V4') if v in seqs]
    identical_pairs=[]
    for i,a in enumerate(testday):
        for b in testday[i+1:]:
            if seqs[a] and seqs[a]==seqs[b]:identical_pairs.append(f'{a}/{b}')
    if identical_pairs:
        review.append({'where':'SUMMATIVE V1-V4','issue':'Same-day parallel forms preserve identical normalized question-family order for '+', '.join(identical_pairs)+'. Scramble family order while keeping connected blocks intact.'})
    # V5/V6 should not be numeric/order-only copies of a same-day form.
    for alt in ('V5','V6'):
        if alt not in seqs:continue
        best=(0.0,None)
        for basev in testday:
            ov=_sequence_overlap(seqs[alt],seqs[basev])
            if ov>best[0]:best=(ov,basev)
        if best[0]>=0.80:
            review.append({'where':f'SUMMATIVE {alt}','issue':f'Normalized question-family overlap with {best[1]} is {best[0]*100:.0f}%. Check that the makeup/alternate form is substantively different, not only numeric/order variation.'})
    times={}
    for v,vals in sorted(versions.items()):
        secs=[]
        for item in vals:
            try:
                if item.get('estimated_time_sec') not in (None,''):secs.append(float(item.get('estimated_time_sec')))
            except Exception:pass
        if secs:
            mins=sum(secs)/60;times[v]=round(mins,1)
            if mins>45.5:sok=False;hard.append({'where':f'SUMMATIVE {v}','issue':f'Estimated time={mins:.1f} min, exceeds ~45 min maximum.'})
    counts['summative_minutes']=times;ck['summative_profile']='PASS' if sok else 'FAIL';counts['figures']=len([p for p in (base/'figures').glob('*') if p.is_file()]) if (base/'figures').exists() else 0;ck['question_review']=f'{len(review)} item/group(s) to inspect' if review else 'PASS';counts['checks']=ck
    return hard,review,counts

def make_zip(base):
    m=re.fullmatch(r'unit(\d+)',base.name,re.I)
    if not m:raise RuntimeError(f'Bank root must be unitN/, found {base.name}')
    out=base.parent/f'unit{m.group(1)}_bank_FINAL.zip'
    if out.exists():out.unlink()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(base.rglob('*')):
            if p.is_file() and '__MACOSX' not in p.parts and p.name not in JUNK_NAMES and not p.name.startswith('._'):z.write(p,(Path(base.name)/p.relative_to(base)).as_posix())
    with zipfile.ZipFile(out) as z:
        bad=z.testzip()
        if bad:raise RuntimeError(f'ZIP CRC failure: {bad}')
    return out

def _human_review_lines(review):
    if not review:return ['- NONE']
    # Collapse repetitive systemic findings; full detail remains in FINALIZER_MACHINE_REPORT.json.
    groups={
        'Internal authoring label leaked':[],
        'Suspiciously large direct-Algebra':[],
    }
    other=[]
    for x in review:
        issue=x.get('issue','')
        matched=False
        for prefix in groups:
            if issue.startswith(prefix):
                groups[prefix].append(x.get('where','?'));matched=True;break
        if not matched:other.append(x)
    lines=[]
    labels={
        'Internal authoring label leaked':'student prompts contain internal authoring labels',
        'Suspiciously large direct-Algebra':'questions use suspiciously large direct-Algebra parameters without an obvious context reason',
    }
    for prefix,ids in groups.items():
        if ids:
            preview=', '.join(ids[:8])+(' ...' if len(ids)>8 else '')
            lines.append(f'- {len(ids)} {labels[prefix]}. First IDs: {preview}')
    lines.extend(f"- {x['where']}: {x['issue']}" for x in other[:40])
    if len(other)>40:lines.append(f'- {len(other)-40} additional review item(s) are in FINALIZER_MACHINE_REPORT.json.')
    return lines

def write_report(base,status,counts,hard,review,graph_ok,cleanup_ok,final_zip=None):
    ck=counts.get('checks',{});lines=['BANK FINALIZER REPORT','='*72,f'Status: {status}',f"Course family: {counts.get('course_family','?')}",'','COMPUTER CHECKS']
    for label,key in [('Required files','required_files'),('HTML / mapping / JSON','html_mapping_json'),('MathJax / HTML','mathjax_html'),('Locked section inventory','locked_inventory'),('Exports','exports'),('Summative profile','summative_profile'),('Question review scan','question_review')]:lines.append(f'- {label}: {ck.get(key,"?")}')
    lines += [f'- Graph generation: {"PASS" if graph_ok else "FAIL"}',f'- Mechanical cleanup: {"PASS" if cleanup_ok else "FAIL"}','','COUNTS',f"- Canonical items: {counts.get('canonical_items','?')}",f"- Sections: {counts.get('sections','?')}",f"- Figures: {counts.get('figures','?')}",f"- Export files: {counts.get('exports','?')}"]
    if counts.get('summative_counts'):lines.append('- Summatives: '+', '.join(f'{v}={n}' for v,n in counts['summative_counts'].items()))
    if counts.get('summative_minutes'):lines.append('- Summative est. minutes: '+', '.join(f'{v}={m}' for v,m in counts['summative_minutes'].items()))
    lines += ['','BROKEN / MUST FIX']+([f"- {x['where']}: {x['issue']}" for x in hard] if hard else ['- NONE'])+['','MIGHT NEED A LOOK']+_human_review_lines(review)
    if final_zip:lines += ['',f'FINAL ZIP: {final_zip.name}']
    rpt=base/'FINALIZER_REPORT.txt';rpt.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (base/'FINALIZER_MACHINE_REPORT.json').write_text(json.dumps({'status':status,'counts':counts,'graph_ok':graph_ok,'cleanup_ok':cleanup_ok,'hard_failures':hard,'review_items':review,'final_zip':str(final_zip) if final_zip else None},indent=2,ensure_ascii=False),encoding='utf-8');return rpt

def main():
    ap=argparse.ArgumentParser(description='Universal Bank finalizer. Run with no argument from inside unitN/, or optionally pass the extracted unitN/ folder.')
    ap.add_argument('source',nargs='?');args=ap.parse_args()
    try:base=resolve_bank_dir(args.source)
    except Exception as e:print(f'BANK FINALIZER STATUS: FAIL\n{e}');return 2
    remove_junk(base);graph=base/'generate_graphs.py';graph_ok=graph.exists()
    if graph_ok:rc,_=run([sys.executable,str(graph)],cwd=base);graph_ok=(rc==0)
    sync_shared_css(base);_,residual=safe_repair_files(base);hard,review,counts=checks(base,residual);cleanup_ok=True
    if not graph_ok:hard.insert(0,{'where':'PACKAGE','issue':'generate_graphs.py is missing or failed.'})
    status='FAIL' if hard else ('REVIEW' if review else 'PASS');final_zip=None
    if not hard:
        try:final_zip=make_zip(base)
        except Exception as e:hard.append({'where':'ZIP','issue':str(e)});status='FAIL'
    rpt=write_report(base,status,counts,hard,review,graph_ok,cleanup_ok,final_zip)
    print(f'BANK FINALIZER STATUS: {status}');print(f'Report: {rpt}')
    if final_zip:print(f'Final ZIP: {final_zip}')
    if review:print(f'Items/groups to look at: {len(review)}')
    return 1 if hard else 0

if __name__=='__main__':raise SystemExit(main())
