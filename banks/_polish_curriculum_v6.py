#!/usr/bin/env python3
"""
~polish_curriculum_v6.py

Deterministic first-pass curriculum polisher.

Purpose
-------
Run safe mechanical repairs and broad structural audits BEFORE the deeper
Tool_Polish_Portable_Memory review.

It is intentionally conservative:
- safe formatting/packaging fixes are automatic
- semantic/content concerns are reported, not guessed
- it does not redesign CSS, rewrite curriculum, or change difficulty

Usage
-----
EASIEST / VS CODE MODE:
    Put this script in the folder you want to polish and press Run.
    With no command-line arguments it polishes THAT FOLDER IN PLACE.

    If ~fix_mathjax_v7.py is in the same folder, it is detected and run first.

Command-line modes still work:

Folder:
    python ~polish_curriculum_v6.py /path/to/folder

ZIP:
    python ~polish_curriculum_v6.py /path/to/package.zip

Single file:
    python ~polish_curriculum_v6.py /path/to/file.html

Optional MathJax fixer:
    python ~polish_curriculum_v6.py package.zip --mathjax-fixer ~fix_mathjax_v7.py

By default, explicit command-line targets preserve originals:
- ZIP -> <name>_polished.zip
- folder -> <name>_polished/
- file -> <name>_polished.<ext>

Use --in-place to overwrite an explicit folder/file target.
"""

from __future__ import annotations

import argparse
import csv
import html as html_lib
import math
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


TEXT_SUFFIXES = {".html", ".htm", ".txt", ".csv", ".py", ".css", ".js", ".md"}
JUNK_NAMES = {".DS_Store", "Thumbs.db"}
JUNK_PREFIXES = ("._",)

# ---------------------------------------------------------------------------
# SAFE FIXES
# ---------------------------------------------------------------------------

SAFE_TEXT_FIXES = [
    (
        re.compile(r"\bPrior-knowledge bridge:\s*", re.IGNORECASE),
        "",
        "removed student-facing 'Prior-knowledge bridge:' meta label",
    ),
    (
        re.compile(r"\bA open circle\b"),
        "An open circle",
        "fixed 'A open circle' grammar",
    ),
    (
        re.compile(r"\ba open circle\b"),
        "an open circle",
        "fixed 'a open circle' grammar",
    ),
    (
        re.compile(r"\bA equipment\b"),
        "An equipment",
        "fixed 'A equipment' grammar",
    ),
    (
        re.compile(r"\ba equipment\b"),
        "an equipment",
        "fixed 'a equipment' grammar",
    ),
    (
        re.compile(r"\b1 meters\b"),
        "1 meter",
        "fixed singular unit '1 meters'",
    ),
    (
        re.compile(r"\b1 centimeters\b"),
        "1 centimeter",
        "fixed singular unit '1 centimeters'",
    ),
    (
        re.compile(r"\b1 millimeters\b"),
        "1 millimeter",
        "fixed singular unit '1 millimeters'",
    ),
    (
        re.compile(r"\b1 seconds\b"),
        "1 second",
        "fixed singular unit '1 seconds'",
    ),
    (
        re.compile(r"\b1 minutes\b"),
        "1 minute",
        "fixed singular unit '1 minutes'",
    ),
    (
        re.compile(r"\b1 hours\b"),
        "1 hour",
        "fixed singular unit '1 hours'",
    ),
    (
        re.compile(r"\b1 units\b"),
        "1 unit",
        "fixed singular unit '1 units'",
    ),
]

GENERIC_FIGCAPTION_RE = re.compile(
    r"<figcaption\b[^>]*>\s*Representation provided for the item\.?\s*</figcaption>",
    re.IGNORECASE | re.DOTALL,
)

ESCAPED_STRUCTURAL_HTML_RE = re.compile(
    r"\\lt\s*/?\s*(?:article|ol|ul|li|div|p|section|details|summary|"
    r"table|thead|tbody|tr|td|th|figure|figcaption)\b",
    re.IGNORECASE,
)

MERGED_RELATION_RE = re.compile(
    r"\\(?:lt|gt|le|ge|ne)[a-pr-zA-PR-Z]"
    r"(?=(?:\^|_|[+\-*/=<>),.;:\]}]|\\|$|\s))"
)

UNRESOLVED_TEMPLATE_PATTERNS = [
    re.compile(r"\{html\.escape\(", re.IGNORECASE),
    re.compile(r"\{\{[^{}]{1,120}\}\}"),
    re.compile(r"\bPLACEHOLDER\b", re.IGNORECASE),
    re.compile(r"\bTODO\b", re.IGNORECASE),
]

META_LANGUAGE_PATTERNS = [
    re.compile(r"\bPrior-knowledge bridge:", re.IGNORECASE),
    re.compile(r"\bRepresentation provided for the item\.?", re.IGNORECASE),
]

# V6 — severity + Notes-specific structural audits.
HARD_FAILURE_MARKERS = (
    "HARD: ",
    "BANK STRUCTURE:",
    "BANK ID RESOLUTION:",
    "broken local reference:",
)

NOTES_FILENAME_RE = re.compile(
    r'^u\d+_\d+_notes(?:_teacher)?\.html$',
    re.IGNORECASE,
)

EXAMPLE_HEADING_RE = re.compile(
    r'<h3\b[^>]*class=["\'][^"\']*\bh-example\b[^"\']*["\'][^>]*>(.*?)</h3>',
    re.IGNORECASE | re.DOTALL,
)
YTI_HEADING_RE = re.compile(
    r'<h3\b[^>]*class=["\'][^"\']*\bh-yti\b[^"\']*["\'][^>]*>(.*?)</h3>',
    re.IGNORECASE | re.DOTALL,
)
FIGURE_BLOCK_RE = re.compile(
    r'<figure\b[^>]*>(.*?)</figure>',
    re.IGNORECASE | re.DOTALL,
)
IMG_TAG_RE = re.compile(r'<img\b[^>]*>', re.IGNORECASE | re.DOTALL)
ALT_ATTR_RE = re.compile(r'\balt=["\']([^"\']*)["\']', re.IGNORECASE | re.DOTALL)
SRC_ATTR_RE = re.compile(r'\bsrc=["\']([^"\']*)["\']', re.IGNORECASE | re.DOTALL)
GENERIC_ALT_RE = re.compile(
    r'^(?:figure|graph|diagram|image|chart|plot|visual|illustration|'
    r'instructional figure(?: for this notes item)?)[\s.:-]*$',
    re.IGNORECASE,
)

ANSWER_SOLUTION_PAIR_RE = re.compile(
    r'<p\b(?P<aattrs>[^>]*)>\s*<strong>\s*Answer:\s*</strong>(?P<answer>.*?)</p>'
    r'\s*<p\b(?P<sattrs>[^>]*)>\s*<strong>\s*Solution:\s*</strong>(?P<solution>.*?)</p>',
    re.IGNORECASE | re.DOTALL,
)


def is_hard_failure(finding: str) -> bool:
    return any(marker in finding for marker in HARD_FAILURE_MARKERS)


def _heading_numbers(matches: list[str], label: str) -> list[int]:
    nums = []
    pattern = re.compile(rf'\b{re.escape(label)}\s+(\d+)\b', re.IGNORECASE)
    for body in matches:
        visible = strip_tags(body)
        m = pattern.search(visible)
        if m:
            nums.append(int(m.group(1)))
    return nums


def audit_notes_html(path: Path, text: str) -> list[str]:
    """Conservative structural/accessibility checks for canonical Notes HTML."""
    findings: list[str] = []
    if not NOTES_FILENAME_RE.match(path.name):
        return findings

    examples = EXAMPLE_HEADING_RE.findall(text)
    ytis = YTI_HEADING_RE.findall(text)
    ex_nums = _heading_numbers(examples, "Example")
    yti_nums = _heading_numbers(ytis, "You Try It")

    if not examples or not ytis:
        findings.append(
            f"HARD: NOTES STRUCTURE: found {len(examples)} real Example heading(s) and "
            f"{len(ytis)} real YTI heading(s)"
        )
    elif len(examples) != len(ytis):
        findings.append(
            f"HARD: NOTES STRUCTURE: {len(examples)} real Example heading(s) vs "
            f"{len(ytis)} real YTI heading(s)"
        )

    if ex_nums and ex_nums != list(range(1, len(ex_nums) + 1)):
        findings.append(
            f"HARD: NOTES STRUCTURE: Example numbering is not contiguous from 1: {ex_nums}"
        )
    if yti_nums and yti_nums != list(range(1, len(yti_nums) + 1)):
        findings.append(
            f"HARD: NOTES STRUCTURE: YTI numbering is not contiguous from 1: {yti_nums}"
        )

    # Student and teacher Notes use the same figures, so report alt-text issues
    # once on the student file rather than duplicating the same review note.
    if "_teacher" not in path.stem.lower():
        generic_alts = []
        for fig in FIGURE_BLOCK_RE.findall(text):
            for img in IMG_TAG_RE.findall(fig):
                alt_m = ALT_ATTR_RE.search(img)
                src_m = SRC_ATTR_RE.search(img)
                alt = html_lib.unescape(alt_m.group(1)).strip() if alt_m else ""
                src = src_m.group(1).strip() if src_m else "[unknown src]"
                if not alt or GENERIC_ALT_RE.match(alt):
                    generic_alts.append(src)
        if generic_alts:
            preview = ", ".join(generic_alts[:5])
            if len(generic_alts) > 5:
                preview += ", ..."
            findings.append(
                f"GENERIC/EMPTY FIGURE ALT TEXT: {len(generic_alts)} instructional figure(s). "
                f"Sample: {preview}"
            )

    if "_teacher" in path.stem.lower():
        duplicate_pairs = 0
        for m in ANSWER_SOLUTION_PAIR_RE.finditer(text):
            attrs = (m.group('aattrs') + ' ' + m.group('sattrs')).lower()
            if 'color:red' not in attrs or 'font-weight:bold' not in attrs:
                continue
            answer = strip_tags(m.group('answer')).strip().casefold()
            solution = strip_tags(m.group('solution')).strip().casefold()
            if answer and answer == solution:
                duplicate_pairs += 1
        if duplicate_pairs:
            findings.append(
                f"REDUNDANT TEACHER ANSWER/SOLUTION: {duplicate_pairs} adjacent pair(s) are identical"
            )

    return findings


def audit_notes_student_teacher_pairs(root: Path) -> list[str]:
    findings: list[str] = []
    students = [
        p for p in root.rglob('u*_notes.html')
        if p.is_file() and NOTES_FILENAME_RE.match(p.name) and '_teacher' not in p.stem.lower()
    ]
    for student in students:
        teacher = student.with_name(student.stem + '_teacher.html')
        if not teacher.exists():
            findings.append(
                f"{student.relative_to(root)} -> HARD: NOTES PAIR MISMATCH: teacher file is missing"
            )
            continue
        st = read_text(student) or ''
        tt = read_text(teacher) or ''
        s_counts = (len(EXAMPLE_HEADING_RE.findall(st)), len(YTI_HEADING_RE.findall(st)))
        t_counts = (len(EXAMPLE_HEADING_RE.findall(tt)), len(YTI_HEADING_RE.findall(tt)))
        if s_counts != t_counts:
            findings.append(
                f"{student.relative_to(root)} -> HARD: NOTES PAIR MISMATCH: "
                f"student EX/YTI={s_counts[0]}/{s_counts[1]} vs "
                f"teacher EX/YTI={t_counts[0]}/{t_counts[1]}"
            )
    return findings

# Simple targeted semantic audit for a known production failure.
# It reports only; it does NOT auto-fix.
GCF_LINEAR_RE = re.compile(
    r"Factor\s+"
    r"(?P<a>-?\d+)\s*[a-zA-Z]"
    r"\s*(?P<sign>[+-])\s*"
    r"(?P<b>\d+)"
    r".{0,80}?"
    r"(?:greatest common factor|GCF)\s+(?P<stated>\d+)",
    re.IGNORECASE | re.DOTALL,
)


def is_junk_path(path: Path) -> bool:
    if "__MACOSX" in path.parts:
        return True
    if path.name in JUNK_NAMES:
        return True
    if any(path.name.startswith(p) for p in JUNK_PREFIXES):
        return True
    return False


def is_polish_helper_script(path: Path) -> bool:
    """
    Exclude the polishing tools themselves from curriculum-content audits.

    Downloaded copies are sometimes prefixed with "~", so normalize that away.
    """
    name = path.name.lstrip("~_").lower()
    return (
        name.startswith("fix_mathjax_v")
        or name.startswith("polish_curriculum_v")
        or name == "run_polish.py"
        or name == "run_all.py"
    )


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except Exception:
            return None
    except Exception:
        return None


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")



NOTES_FIGURE_OPEN_RE = re.compile(
    r'(?P<open><figure\b(?P<fattrs>[^>]*)>)'
    r'(?P<ws>\s*)'
    r'(?P<imgopen><img\b(?P<iattrs>[^>]*)>)',
    re.IGNORECASE,
)
CLASS_ATTR_RE = re.compile(
    r'\sclass=(?P<q>["\'])(?P<classes>[^"\']*)(?P=q)',
    re.IGNORECASE,
)
NOTES_FIGURE_CLASS_RE = re.compile(r'^(?:notes-figure|wu-img-\d{3})$')


def move_notes_figure_classes(text: str) -> tuple[str, int]:
    """
    Repair the common Notes HTML mistake:
      <figure><img class="notes-figure wu-img-500" ...></figure>

    Canonical notes.css expects:
      <figure class="notes-figure wu-img-500"><img ...></figure>

    Only notes-figure / wu-img-NNN tokens move. Any unrelated img classes stay.
    """
    moved_blocks = 0

    def repl(m: re.Match) -> str:
        nonlocal moved_blocks
        fattrs = m.group("fattrs")
        iattrs = m.group("iattrs")

        icm = CLASS_ATTR_RE.search(iattrs)
        if not icm:
            return m.group(0)

        img_classes = icm.group("classes").split()
        move = [c for c in img_classes if NOTES_FIGURE_CLASS_RE.match(c)]
        if not move:
            return m.group(0)

        remain = [c for c in img_classes if c not in move]

        # Remove/rebuild class on the img.
        if remain:
            new_img_class = f' class={icm.group("q")}{" ".join(remain)}{icm.group("q")}'
        else:
            new_img_class = ""
        iattrs = iattrs[:icm.start()] + new_img_class + iattrs[icm.end():]

        # Merge moved tokens into any existing figure class.
        fcm = CLASS_ATTR_RE.search(fattrs)
        if fcm:
            existing = fcm.group("classes").split()
            merged = existing + [c for c in move if c not in existing]
            new_fclass = f' class={fcm.group("q")}{" ".join(merged)}{fcm.group("q")}'
            fattrs = fattrs[:fcm.start()] + new_fclass + fattrs[fcm.end():]
        else:
            fattrs = fattrs + f' class="{" ".join(move)}"'

        moved_blocks += 1
        return f"<figure{fattrs}>{m.group('ws')}<img{iattrs}>"

    return NOTES_FIGURE_OPEN_RE.sub(repl, text), moved_blocks


def safe_polish_text(path: Path, text: str) -> tuple[str, list[str]]:
    fixes: list[str] = []

    # Exact generic figure-caption removal is safe and HTML-only.
    if path.suffix.lower() in {".html", ".htm"}:
        n = len(GENERIC_FIGCAPTION_RE.findall(text))
        if n:
            text = GENERIC_FIGCAPTION_RE.sub("", text)
            fixes.append(f"{n}x removed generic figure caption")

        text, n = move_notes_figure_classes(text)
        if n:
            fixes.append(
                f"{n}x moved notes-figure / wu-img class(es) from img to parent figure"
            )

    # Avoid rewriting Python/JS/CSS prose patterns.
    if path.suffix.lower() in {".html", ".htm", ".txt", ".csv", ".md"}:
        for pattern, replacement, label in SAFE_TEXT_FIXES:
            n = len(pattern.findall(text))
            if n:
                text = pattern.sub(replacement, text)
                fixes.append(f"{n}x {label}")

    return text, fixes


# ---------------------------------------------------------------------------
# AUDITS
# ---------------------------------------------------------------------------

def unescaped_dollar_count(text: str) -> int:
    return len(re.findall(r"(?<!\\)\$", text))


def strip_tags(fragment: str) -> str:
    fragment = re.sub(
        r"<details\b[^>]*class=[\"'][^\"']*teacher-only[^\"']*[\"'][^>]*>.*?</details>",
        " ",
        fragment,
        flags=re.IGNORECASE | re.DOTALL,
    )
    fragment = re.sub(
        r"<[^>]+>",
        " ",
        fragment,
        flags=re.DOTALL,
    )
    fragment = html_lib.unescape(fragment)
    return " ".join(fragment.split())


def normalize_prompt(text: str) -> str:
    text = text.lower()
    # Strip common Bank metadata that may be visible in article headers.
    text = re.sub(r"\bu\d+-s\d+-[a-z0-9-]+\b", " ", text)
    text = re.sub(
        r"\b(?:notes example|notes yti|practice set \d|extra practice|"
        r"warm[- ]?up \d|exit ticket [abc]|blooket|tarsia|cyu|"
        r"what'?s to come|unit review|summative v\d|dok \d)\b",
        " ",
        text,
    )
    text = re.sub(r"\bu\d+-mg\d+\b", " ", text)
    text = re.sub(r"[^a-z0-9\\$+\-*/=<>^_.]+", " ", text)
    return " ".join(text.split())


def audit_bank_html(html_path: Path, text: str) -> list[str]:
    warnings: list[str] = []

    # Parse each complete Bank article. Do not search for a loose "id=" token
    # because attributes such as data-mastery-goal-id= also contain that text.
    article_ids: list[str] = []
    article_bodies: list[tuple[str, str]] = []

    for m in re.finditer(
        r"<article\b(?P<attrs>[^>]*)>(?P<body>.*?)</article>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        attrs = m.group("attrs")
        body = m.group("body")

        if not re.search(
            r'class=["\'][^"\']*\bbank-item\b[^"\']*["\']',
            attrs,
            re.IGNORECASE,
        ):
            continue

        # Prefer canonical data-bank-id; fall back to the REAL id attribute.
        bank_id_match = re.search(
            r'\bdata-bank-id=["\']([^"\']+)["\']',
            attrs,
            re.IGNORECASE,
        )
        if bank_id_match:
            item_id = bank_id_match.group(1)
        else:
            id_match = re.search(
                r'(?:^|\s)id=["\']([^"\']+)["\']',
                attrs,
                re.IGNORECASE,
            )
            if not id_match:
                continue
            item_id = id_match.group(1)

        article_ids.append(item_id)
        article_bodies.append((item_id, body))

    # Mapping CSV in same directory.
    mappings = list(html_path.parent.glob("*_mapping.csv"))
    for mapping in mappings:
        try:
            with mapping.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        except Exception as exc:
            warnings.append(f"could not read mapping CSV {mapping.name}: {exc}")
            continue

        if len(rows) != len(article_ids):
            warnings.append(
                f"BANK STRUCTURE: {len(article_ids)} real bank-item articles vs "
                f"{len(rows)} mapping rows in {mapping.name}"
            )

        if rows:
            keys = list(rows[0].keys())
            id_key = next(
                (
                    k for k in keys
                    if (k or "").strip().lower()
                    in {"bank_id", "bank item id", "item_id", "id"}
                ),
                None,
            )
            if id_key:
                mapped_ids = [
                    r.get(id_key, "").strip()
                    for r in rows
                    if r.get(id_key)
                ]
                html_counts = Counter(article_ids)
                unresolved = [x for x in mapped_ids if html_counts[x] != 1]
                if unresolved:
                    preview = ", ".join(unresolved[:5])
                    if len(unresolved) > 5:
                        preview += ", ..."
                    warnings.append(
                        f"BANK ID RESOLUTION: {len(unresolved)} mapped ID(s) "
                        f"do not resolve exactly once. Sample: {preview}"
                    )

    # Cross-destination exact-prompt candidate audit.
    # Only inspect the student-facing portion of each article. Teacher answers
    # are intentionally excluded from the duplicate comparison.
    normalized_to_ids: dict[str, list[str]] = defaultdict(list)
    for item_id, body in article_bodies:
        student_body = body.split(
            '<details class="teacher-answer"',
            1,
        )[0]
        visible = strip_tags(student_body)
        norm = normalize_prompt(visible)
        if len(norm) >= 20:
            normalized_to_ids[norm].append(item_id)

    duplicate_groups = [
        ids for ids in normalized_to_ids.values()
        if len(ids) > 1
    ]
    if duplicate_groups:
        total_extra = sum(len(ids) - 1 for ids in duplicate_groups)
        sample = "; ".join(
            ", ".join(ids[:4])
            for ids in duplicate_groups[:5]
        )
        warnings.append(
            f"EXACT/NEAR PROMPT DUPLICATION CANDIDATES: "
            f"{len(duplicate_groups)} group(s), {total_extra} extra copy/copies. "
            f"Sample: {sample}"
        )

    return warnings

def audit_text_file(path: Path, text: str) -> list[str]:
    warnings: list[str] = []

    if path.suffix.lower() in {".html", ".htm", ".txt", ".csv"}:
        if unescaped_dollar_count(text) % 2:
            warnings.append("HARD: odd number of unescaped $ delimiters")

    n = len(ESCAPED_STRUCTURAL_HTML_RE.findall(text))
    if n:
        warnings.append(f"HARD: {n} escaped structural HTML tag pattern(s) remain")

    n = len(MERGED_RELATION_RE.findall(text))
    if n:
        warnings.append(f"{n} merged TeX relation command(s) remain")

    # Template/TODO scans are aimed at deployable student/resource text.
    # Python/CSS/JS legitimately contain braces and development comments.
    # BUILD_REPORT also legitimately names words such as PLACEHOLDER while
    # documenting that the actual resource was checked.
    if (
        path.suffix.lower() in {".html", ".htm", ".txt", ".csv", ".md"}
        and path.name.upper() not in {"BUILD_REPORT.TXT", "POLISH_REPORT.TXT", "DETERMINISTIC_POLISH_REPORT.TXT"}
    ):
        for pat in UNRESOLVED_TEMPLATE_PATTERNS:
            n = len(pat.findall(text))
            if n:
                warnings.append(f"HARD: {n} unresolved template/TODO pattern(s): {pat.pattern}")

    for pat in META_LANGUAGE_PATTERNS:
        n = len(pat.findall(text))
        if n:
            warnings.append(f"{n} student-facing meta/filler phrase occurrence(s): {pat.pattern}")

    # Targeted GCF semantic audit.
    for m in GCF_LINEAR_RE.finditer(text):
        a = abs(int(m.group("a")))
        b = abs(int(m.group("b")))
        stated = int(m.group("stated"))
        actual = math.gcd(a, b)
        if stated != actual:
            excerpt = " ".join(m.group(0).split())[:180]
            warnings.append(
                f"GCF CLAIM MISMATCH: stated {stated}, actual gcd({a},{b})={actual}: {excerpt}"
            )

    if path.suffix.lower() in {".html", ".htm"}:
        bad_notes_fig = len(re.findall(
            r'<figure\b[^>]*>\s*<img\b[^>]*class=["\'][^"\']*\bnotes-figure\b',
            text,
            flags=re.IGNORECASE,
        ))
        if bad_notes_fig:
            warnings.append(
                f"{bad_notes_fig} Notes figure(s) still place notes-figure on <img> instead of <figure>"
            )

        warnings.extend(audit_notes_html(path, text))
        warnings.extend(audit_bank_html(path, text))

    return warnings



def audit_summative_source_maps(root: Path) -> list[str]:
    """
    Check internal metadata consistency in *_summative_source_map.csv files.

    Current important check:
      calculator_rule should not contradict an explicit notes value of
      "calculator-permitted" or "non-calculator".

    This is audit-only. It does not guess which field is authoritative.
    """
    warnings: list[str] = []

    for path in root.rglob("*_summative_source_map.csv"):
        if is_junk_path(path):
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        except Exception as exc:
            warnings.append(
                f"{path.relative_to(root)} -> could not read source map: {exc}"
            )
            continue

        mismatches = []
        for row in rows:
            rule = (row.get("calculator_rule") or "").strip().lower()
            note = (row.get("notes") or "").strip().lower()
            if note in {"calculator-permitted", "non-calculator"} and rule:
                if rule != note:
                    mismatches.append(
                        (
                            row.get("version", ""),
                            row.get("displayed_item_number", ""),
                            row.get("bank_id", ""),
                            rule,
                            note,
                        )
                    )

        if mismatches:
            sample = "; ".join(
                f"{v} Q{q} {bid}: calculator_rule={rule}, notes={note}"
                for v, q, bid, rule, note in mismatches[:5]
            )
            if len(mismatches) > 5:
                sample += "; ..."
            warnings.append(
                f"{path.relative_to(root)} -> SUMMATIVE CALCULATOR METADATA: "
                f"{len(mismatches)} row(s) have contradictory calculator_rule "
                f"and notes values. Sample: {sample}"
            )

    return warnings

def audit_local_links(root: Path) -> list[str]:
    warnings: list[str] = []
    attr_re = re.compile(r"""(?:src|href)=["']([^"']+)["']""", re.IGNORECASE)
    for path in root.rglob("*.html"):
        text = read_text(path)
        if text is None:
            continue
        for target in attr_re.findall(text):
            target = target.strip()
            if (
                not target
                or target.startswith("#")
                or re.match(r"^[a-z]+://", target, re.I)
                or target.startswith(("mailto:", "javascript:", "data:"))
            ):
                continue
            clean = target.split("#", 1)[0].split("?", 1)[0]
            if not clean:
                continue
            resolved = (path.parent / clean).resolve()

            # A curriculum sub-package may intentionally link upward to shared
            # course-root CSS/resources that are not bundled in this ZIP
            # (for example ../../css/base.css from banks/unit1/unit1.html).
            # If the resolved path leaves the supplied polish root, treat it as
            # a deployment-relative dependency rather than a broken local link.
            try:
                resolved.relative_to(root.resolve())
                inside_supplied_root = True
            except ValueError:
                inside_supplied_root = False

            if inside_supplied_root and not resolved.exists():
                warnings.append(f"{path.relative_to(root)} -> broken local reference: {target}")
    return warnings


# ---------------------------------------------------------------------------
# FILE / FOLDER PROCESSING
# ---------------------------------------------------------------------------

def remove_junk(root: Path) -> list[str]:
    removed: list[str] = []
    # Deepest first.
    for p in sorted(root.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if is_junk_path(p):
            try:
                rel = str(p.relative_to(root))
            except Exception:
                rel = str(p)
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass
            removed.append(rel)
    return removed


def run_mathjax_fixer(root: Path, fixer: Path | None) -> list[str]:
    lines: list[str] = []
    if fixer is None:
        return lines
    if not fixer.exists():
        return [f"MathJax fixer not found: {fixer}"]
    try:
        proc = subprocess.run(
            [sys.executable, str(fixer), str(root)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        lines.append(f"MathJax fixer return code: {proc.returncode}")
        if proc.stdout.strip():
            lines.extend("  " + x for x in proc.stdout.strip().splitlines()[-12:])
        if proc.returncode != 0 and proc.stderr.strip():
            lines.extend("  STDERR: " + x for x in proc.stderr.strip().splitlines()[-8:])
    except Exception as exc:
        lines.append(f"MathJax fixer failed: {exc}")
    return lines


def polish_tree(root: Path, fixer: Path | None) -> tuple[list[str], list[str]]:
    fixes: list[str] = []
    warnings: list[str] = []

    removed = remove_junk(root)
    if removed:
        fixes.append(f"removed {len(removed)} junk/system path(s)")

    mathjax_log = run_mathjax_fixer(root, fixer)
    if mathjax_log:
        fixes.append("ran supplied MathJax fixer")
        fixes.extend(mathjax_log)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or is_junk_path(path):
            continue
        if is_polish_helper_script(path):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_text(path)
        if text is None:
            continue

        new_text, file_fixes = safe_polish_text(path, text)
        if new_text != text:
            write_text(path, new_text)
            for f in file_fixes:
                fixes.append(f"{path.relative_to(root)}: {f}")
            text = new_text

        for warning in audit_text_file(path, text):
            warnings.append(f"{path.relative_to(root)}: {warning}")

    warnings.extend(audit_local_links(root))
    warnings.extend(audit_summative_source_maps(root))
    warnings.extend(audit_notes_student_teacher_pairs(root))
    return fixes, warnings


def report_text(target_label: str, fixes: list[str], warnings: list[str]) -> str:
    hard = [w for w in warnings if is_hard_failure(w)]
    review = [w for w in warnings if not is_hard_failure(w)]

    if hard:
        status = "FAIL — DO NOT DEPLOY"
    elif review:
        status = "PASS WITH REVIEW NOTES"
    else:
        status = "PASS"

    lines = [
        "DETERMINISTIC POLISH REPORT",
        "=" * 72,
        f"Target: {target_label}",
        "",
        "SAFE AUTOMATIC FIXES",
    ]
    if fixes:
        lines.extend(f"  - {x}" for x in fixes)
    else:
        lines.append("  - NONE")

    lines.extend(["", "HARD FAILURES"])
    if hard:
        lines.extend(f"  - {x}" for x in hard)
    else:
        lines.append("  - NONE")

    lines.extend(["", "REVIEW NOTES"])
    if review:
        lines.extend(f"  - {x}" for x in review)
    else:
        lines.append("  - NONE")

    lines.extend([
        "",
        "STATUS",
        f"  {status}",
        "",
        "NOTE",
        "  This script is a deterministic first pass. Semantic/curriculum review",
        "  should still be completed with Tool_Polish_Portable_Memory.txt.",
        "",
    ])
    return "\n".join(lines)


def useful_zip_roots(extract_dir: Path) -> list[Path]:
    roots = [
        p for p in extract_dir.iterdir()
        if not is_junk_path(p)
    ]
    return roots


def zip_directory(source_dir: Path, output_zip: Path, include_root: bool = True) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        base = source_dir.parent if include_root else source_dir
        for p in sorted(source_dir.rglob("*")):
            if is_junk_path(p):
                continue
            if p.is_file():
                z.write(p, p.relative_to(base))


def process_zip(target: Path, output: Path | None, fixer: Path | None) -> Path:
    with tempfile.TemporaryDirectory(prefix="curriculum_polish_") as td:
        extract_dir = Path(td) / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(target) as z:
            z.extractall(extract_dir)

        roots = useful_zip_roots(extract_dir)
        # Process entire extraction tree so multi-root packages are supported.
        fixes, warnings = polish_tree(extract_dir, fixer)

        report = report_text(target.name, fixes, warnings)

        # Put report inside the single useful root when possible; otherwise root.
        if len(roots) == 1 and roots[0].is_dir():
            report_path = roots[0] / "DETERMINISTIC_POLISH_REPORT.txt"
        else:
            report_path = extract_dir / "DETERMINISTIC_POLISH_REPORT.txt"
        report_path.write_text(report, encoding="utf-8")

        if output is None:
            output = target.with_name(target.stem + "_polished.zip")

        # Rezip all useful roots, excluding junk.
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(extract_dir.rglob("*")):
                if is_junk_path(p):
                    continue
                if p.is_file():
                    z.write(p, p.relative_to(extract_dir))

    return output


def process_folder(target: Path, output: Path | None, fixer: Path | None, in_place: bool) -> Path:
    if in_place:
        work = target
    else:
        if output is None:
            output = target.with_name(target.name + "_polished")
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(target, output)
        work = output

    fixes, warnings = polish_tree(work, fixer)
    (work / "DETERMINISTIC_POLISH_REPORT.txt").write_text(
        report_text(target.name, fixes, warnings),
        encoding="utf-8",
    )
    return work


def process_file(target: Path, output: Path | None, fixer: Path | None, in_place: bool) -> Path:
    if in_place:
        work = target
    else:
        if output is None:
            output = target.with_name(target.stem + "_polished" + target.suffix)
        shutil.copy2(target, output)
        work = output

    # For a single file, run safe text repairs and audits only.
    text = read_text(work)
    fixes: list[str] = []
    warnings: list[str] = []
    if text is not None:
        new_text, f = safe_polish_text(work, text)
        if new_text != text:
            write_text(work, new_text)
            fixes.extend(f)
            text = new_text
        warnings.extend(audit_text_file(work, text))

    report_path = work.with_name(work.stem + "_DETERMINISTIC_POLISH_REPORT.txt")
    report_path.write_text(report_text(target.name, fixes, warnings), encoding="utf-8")
    return work


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic curriculum polishing first pass.")
    parser.add_argument(
        "target",
        nargs="?",
        type=Path,
        default=None,
        help="ZIP, folder, or single file. If omitted, polish this script's folder in place.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional output path")
    parser.add_argument(
        "--mathjax-fixer",
        type=Path,
        default=None,
        help="Optional ~fix_mathjax_v7.py (or newer) path",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Modify folder/file in place. ZIP input always produces a new ZIP.",
    )
    args = parser.parse_args()

    # VS Code / double-click style:
    # no positional target -> polish the folder containing this script.
    auto_folder_mode = args.target is None
    if auto_folder_mode:
        target = Path(__file__).resolve().parent
        args.in_place = True
        print("=" * 72)
        print("VS CODE MODE")
        print(f"Polishing this folder in place:\n  {target}")
        print("=" * 72)
    else:
        target = args.target.expanduser().resolve()

    if not target.exists():
        print(f"Target not found: {target}", file=sys.stderr)
        return 2

    # If no fixer was explicitly supplied, automatically use the highest-numbered fix_mathjax_v*.py next to this script.
    if args.mathjax_fixer:
        fixer = args.mathjax_fixer.expanduser().resolve()
    else:
        script_dir = Path(__file__).resolve().parent
        fixer_candidates = sorted(
            [
                p for p in script_dir.glob("*fix_mathjax_v*.py")
                if p.is_file() and p.name.lstrip("~_").startswith("fix_mathjax_v")
            ],
            key=lambda p: (
                int(re.search(r"_v(\d+)", p.stem).group(1))
                if re.search(r"_v(\d+)", p.stem)
                else -1
            ),
        )
        fixer = fixer_candidates[-1] if fixer_candidates else None
        if fixer:
            print(f"Auto-detected MathJax fixer: {fixer.name}")

    output = args.output.expanduser().resolve() if args.output else None

    if target.is_file() and target.suffix.lower() == ".zip":
        result = process_zip(target, output, fixer)
    elif target.is_dir():
        result = process_folder(target, output, fixer, args.in_place)
    elif target.is_file():
        result = process_file(target, output, fixer, args.in_place)
    else:
        print(f"Unsupported target: {target}", file=sys.stderr)
        return 2

    print()
    print("=" * 72)
    print("POLISH COMPLETE")
    print(f"Output: {result}")
    if target.is_dir():
        print(f"Report: {result / 'DETERMINISTIC_POLISH_REPORT.txt'}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
