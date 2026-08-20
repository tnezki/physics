#!/usr/bin/env python3
"""
polish_curriculum_v2.py

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

    If fix_mathjax_v5.py is in the same folder, it is detected and run first.

Command-line modes still work:

Folder:
    python polish_curriculum_v2.py /path/to/folder

ZIP:
    python polish_curriculum_v2.py /path/to/package.zip

Single file:
    python polish_curriculum_v2.py /path/to/file.html

Optional MathJax fixer:
    python polish_curriculum_v2.py package.zip --mathjax-fixer fix_mathjax_v5.py

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


def safe_polish_text(path: Path, text: str) -> tuple[str, list[str]]:
    fixes: list[str] = []

    # Exact generic figure-caption removal is safe and HTML-only.
    if path.suffix.lower() in {".html", ".htm"}:
        n = len(GENERIC_FIGCAPTION_RE.findall(text))
        if n:
            text = GENERIC_FIGCAPTION_RE.sub("", text)
            fixes.append(f"{n}x removed generic figure caption")

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

    article_matches = list(
        re.finditer(
            r"<article\b[^>]*class=[\"'][^\"']*\bbank-item\b[^\"']*[\"'][^>]*"
            r"id=[\"']([^\"']+)[\"'][^>]*>(.*?)</article>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    # Some generators place id before class. Fall back to article extraction.
    if not article_matches:
        article_matches = []
        for m in re.finditer(
            r"<article\b([^>]*)>(.*?)</article>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            attrs, body = m.group(1), m.group(2)
            if not re.search(r"class=[\"'][^\"']*\bbank-item\b", attrs, re.I):
                continue
            idm = re.search(r"\bid=[\"']([^\"']+)[\"']", attrs, re.I)
            if idm:
                # synthesize a tuple-like small object by storing directly below
                article_matches.append((idm.group(1), body))

    article_ids: list[str] = []
    article_bodies: list[tuple[str, str]] = []
    if article_matches and hasattr(article_matches[0], "group"):
        for m in article_matches:
            article_ids.append(m.group(1))
            article_bodies.append((m.group(1), m.group(2)))
    else:
        for item_id, body in article_matches:
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

        # Resolve likely ID column.
        if rows:
            keys = list(rows[0].keys())
            id_key = next(
                (k for k in keys if (k or "").strip().lower() in {"bank_id", "bank item id", "item_id", "id"}),
                None,
            )
            if id_key:
                mapped_ids = [r.get(id_key, "").strip() for r in rows if r.get(id_key)]
                html_counts = Counter(article_ids)
                unresolved = [x for x in mapped_ids if html_counts[x] != 1]
                if unresolved:
                    warnings.append(
                        f"BANK ID RESOLUTION: {len(unresolved)} mapped ID(s) do not resolve exactly once"
                    )

    # Rough cross-destination exact prompt duplicate audit.
    normalized_to_ids: dict[str, list[str]] = defaultdict(list)
    for item_id, body in article_bodies:
        visible = strip_tags(body)
        norm = normalize_prompt(visible)
        if len(norm) >= 20:
            normalized_to_ids[norm].append(item_id)

    duplicate_groups = [ids for ids in normalized_to_ids.values() if len(ids) > 1]
    if duplicate_groups:
        total_extra = sum(len(ids) - 1 for ids in duplicate_groups)
        sample = "; ".join(", ".join(ids[:4]) for ids in duplicate_groups[:5])
        warnings.append(
            f"EXACT/NEAR PROMPT DUPLICATION CANDIDATES: {len(duplicate_groups)} group(s), "
            f"{total_extra} extra copy/copies. Sample: {sample}"
        )

    return warnings


def audit_text_file(path: Path, text: str) -> list[str]:
    warnings: list[str] = []

    if path.suffix.lower() in {".html", ".htm", ".txt", ".csv"}:
        if unescaped_dollar_count(text) % 2:
            warnings.append("odd number of unescaped $ delimiters")

    n = len(ESCAPED_STRUCTURAL_HTML_RE.findall(text))
    if n:
        warnings.append(f"{n} escaped structural HTML tag pattern(s) remain")

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
                warnings.append(f"{n} unresolved template/TODO pattern(s): {pat.pattern}")

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
        warnings.extend(audit_bank_html(path, text))

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
    return fixes, warnings


def report_text(target_label: str, fixes: list[str], warnings: list[str]) -> str:
    status = "PASS" if not warnings else "PASS WITH REVIEW NOTES"
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

    lines.extend(["", "AUDIT / REVIEW NOTES"])
    if warnings:
        lines.extend(f"  - {x}" for x in warnings)
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
        help="Optional fix_mathjax_v5.py (or newer) path",
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

    # If no fixer was explicitly supplied, automatically use fix_mathjax_v5.py
    # (or the highest-numbered fix_mathjax_v*.py) next to this script.
    if args.mathjax_fixer:
        fixer = args.mathjax_fixer.expanduser().resolve()
    else:
        script_dir = Path(__file__).resolve().parent
        fixer_candidates = sorted(
            script_dir.glob("fix_mathjax_v*.py"),
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
