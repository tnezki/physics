#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import threading
import webbrowser
from copy import deepcopy
from datetime import date, datetime
from html import escape
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

HOST = "127.0.0.1"
PORT = 8768
PLANNER_VERSION = "0.1.1"
HERE = Path(__file__).resolve().parent
TEACHER_TOOLS_ROOT = HERE.parent
GITHUB_ROOT = HERE.parents[1]
PHYSICS_ROOT = GITHUB_ROOT / "physics"
AGENDA_PATH = PHYSICS_ROOT / "agenda" / "index.html"
SHARED_ROOT = GITHUB_ROOT / "teacher_shared"
SHARED_PHYSICS_ROOT = SHARED_ROOT / "physics"
SHARED_INDEX = SHARED_PHYSICS_ROOT / "index.html"
PRIVATE_ARTIFACTS = SHARED_PHYSICS_ROOT / "data" / "private_artifacts.json"
STATE_PATH = HERE / "planner_state.json"
QUICK_CHECK_LIBRARY = PHYSICS_ROOT / "quick_check____htq5855" / "library.json"
PUBLIC_BASE = "https://tnezki.github.io/physics/"

STUDENT_RESOURCE_OPTIONS = [
    "", "Warm Up", "Notes", "Investigation", "Activity", "Demo",
    "Performance Task", "Practice Set", "Extra Practice", "Quick Check", "Review", "Custom Item",
]
DAY_CONTROLS = [
    "Regular Day", "Insert Blank Day", "Bump Back", "Snow Day", "P.D.",
    "1/2 Day", "Break", "No School", "Assembly Schedule", "Testing", "Sub Assignment",
]
SHIFTING_CONTROLS = {
    "Insert Blank Day", "Snow Day", "P.D.", "Break", "No School"
}
BLOCKED_CONTROLS = {"Snow Day", "P.D.", "Break", "No School"}
EDITOR_DAY_CONTROLS = list(DAY_CONTROLS)




def _git_run(repo: Path, args: list[str], timeout: int = 120) -> tuple[int, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        ["/usr/bin/git", *args],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        timeout=timeout,
    )
    return proc.returncode, (proc.stdout or "").strip()


def _git_repositories() -> list[Path]:
    repos = []
    if not GITHUB_ROOT.is_dir():
        return repos
    for child in sorted(GITHUB_ROOT.iterdir(), key=lambda x: x.name.casefold()):
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            continue
        if (child / ".git").exists():
            repos.append(child)
    return repos


def git_pull_all() -> dict:
    results = []
    for repo in _git_repositories():
        code, branch = _git_run(repo, ["branch", "--show-current"], timeout=20)
        branch = branch.strip() if code == 0 else ""
        if not branch:
            results.append({"repo": repo.name, "ok": False, "detail": "Skipped: no current branch."})
            continue
        code, remote = _git_run(repo, ["remote", "get-url", "origin"], timeout=20)
        if code != 0:
            results.append({"repo": repo.name, "ok": False, "detail": "Skipped: no origin remote."})
            continue
        code, out = _git_run(repo, ["pull", "--rebase", "--autostash"], timeout=180)
        results.append({"repo": repo.name, "ok": code == 0, "detail": out or ("Up to date." if code == 0 else "Pull failed.")})
    failed = [r for r in results if not r["ok"]]
    return {
        "ok": not failed,
        "action": "pull",
        "results": results,
        "message": (
            f"Pulled {len(results)} GitHub repos." if not failed
            else f"Pull finished with {len(failed)} repo(s) needing attention: " + ", ".join(r["repo"] for r in failed)
        ),
    }


def git_push_all() -> dict:
    results = []
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    for repo in _git_repositories():
        code, branch = _git_run(repo, ["branch", "--show-current"], timeout=20)
        branch = branch.strip() if code == 0 else ""
        if not branch:
            results.append({"repo": repo.name, "ok": False, "detail": "Skipped: no current branch."})
            continue
        code, remote = _git_run(repo, ["remote", "get-url", "origin"], timeout=20)
        if code != 0:
            results.append({"repo": repo.name, "ok": False, "detail": "Skipped: no origin remote."})
            continue
        code, out = _git_run(repo, ["add", "-A"], timeout=60)
        if code != 0:
            results.append({"repo": repo.name, "ok": False, "detail": out or "git add failed."})
            continue
        code, staged = _git_run(repo, ["diff", "--cached", "--quiet"], timeout=30)
        if code == 1:
            code, out = _git_run(repo, ["commit", "-m", f"Teacher Tools sync {stamp}"], timeout=120)
            if code != 0:
                results.append({"repo": repo.name, "ok": False, "detail": out or "Commit failed."})
                continue
        elif code not in (0, 1):
            results.append({"repo": repo.name, "ok": False, "detail": staged or "Could not inspect staged changes."})
            continue
        code, out = _git_run(repo, ["pull", "--rebase"], timeout=180)
        if code != 0:
            results.append({"repo": repo.name, "ok": False, "detail": out or "Pull before push failed."})
            continue
        code, out = _git_run(repo, ["push"], timeout=180)
        results.append({"repo": repo.name, "ok": code == 0, "detail": out or ("Pushed." if code == 0 else "Push failed.")})
    failed = [r for r in results if not r["ok"]]
    return {
        "ok": not failed,
        "action": "push",
        "results": results,
        "message": (
            f"Committed and pushed {len(results)} GitHub repos." if not failed
            else f"Push finished with {len(failed)} repo(s) needing attention: " + ", ".join(r["repo"] for r in failed)
        ),
    }

def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def _merge_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if src.is_file():
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
        return
    dst.mkdir(parents=True, exist_ok=True)
    for child in list(src.iterdir()):
        _merge_tree(child, dst / child.name)
    try:
        src.rmdir()
    except OSError:
        pass


def _rewrite_secure_assessment_assets(path: Path) -> None:
    """Keep secure assessment HTML private while loading non-secure shared CSS/images publicly."""
    if not path.is_file() or path.suffix.lower() != ".html":
        return
    text = path.read_text(encoding="utf-8")
    rewritten = re.sub(
        r'(?P<attr>\b(?:src|href))=(?P<quote>["\'])\.\./\.\./',
        lambda m: f'{m.group("attr")}={m.group("quote")}{PUBLIC_BASE}',
        text,
    )
    if rewritten != text:
        atomic_write_text(path, rewritten)


def _move_tree_secure(src: Path, dst: Path) -> None:
    """Move one public secure-artifact tree into teacher_shared without overwriting existing private files."""
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for child in list(src.iterdir()):
        target = dst / child.name
        if child.is_dir():
            _move_tree_secure(child, target)
            try:
                child.rmdir()
            except OSError:
                pass
            continue
        if target.exists():
            if target.is_file() and target.read_bytes() == child.read_bytes():
                child.unlink()
                continue
            stem, suffix = target.stem, target.suffix
            index = 2
            while True:
                alternate = target.with_name(f"{stem}_migrated_{index}{suffix}")
                if not alternate.exists():
                    target = alternate
                    break
                index += 1
        child.rename(target)
    try:
        src.rmdir()
    except OSError:
        pass


def migrate_secure_summatives() -> None:
    """Move any Physics unit summatives out of the public repo into teacher_shared/physics/assessments."""
    secure_root = SHARED_PHYSICS_ROOT / "assessments"
    secure_root.mkdir(parents=True, exist_ok=True)
    # assessment_plans is the current public folder name. The legacy name is retained only for one-time cleanup.
    for public_root in (PHYSICS_ROOT / "assessment_plans", PHYSICS_ROOT / "assessments_zxrtjp"):
        if not public_root.is_dir():
            continue
        for unit in range(1, 9):
            src = public_root / f"unit{unit}_summative"
            if not src.exists():
                continue
            dst = secure_root / f"unit{unit}_summative"
            _move_tree_secure(src, dst)
            for html_path in dst.rglob("*.html"):
                _rewrite_secure_assessment_assets(html_path)


def _secure_assessments(unit: int) -> str:
    folder = SHARED_PHYSICS_ROOT / "assessments" / f"unit{unit}_summative"
    if not folder.is_dir():
        return f'<p class="placeholder">No approved Unit {unit} secure assessments are listed yet.</p>'
    files = sorted(folder.glob("*.html"), key=lambda p: p.name.casefold())
    if not files:
        return f'<p class="placeholder">No approved Unit {unit} secure assessments are listed yet.</p>'
    rows = []
    for path in files:
        label = path.stem.replace("_", " ").title()
        href = f'../../assessments/unit{unit}_summative/{quote(path.name)}'
        rows.append(f'<li><a href="{href}" target="_blank" rel="noopener">{escape(label)}</a></li>')
    return '<ul>' + ''.join(rows) + '</ul>'


def build_teacher_shared_home() -> str:
    return """<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Teacher Shared</title><style>body{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f4f6f8;color:#173f6d}.wrap{max-width:900px;margin:48px auto;padding:0 20px}h1{background:#173f6d;color:#fff;padding:20px;border-radius:14px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.card{display:block;background:#fff;border:2px solid #d9c06d;border-radius:14px;padding:24px;text-decoration:none;color:#173f6d;font-size:1.2rem;font-weight:800}.card:hover{background:#fff8df}.muted{color:#667085;font-size:.9rem}</style></head><body><div class=\"wrap\"><h1>Teacher Shared</h1><div class=\"cards\"><a class=\"card\" href=\"algebra/index.html\">Algebra 1</a><a class=\"card\" href=\"physics/index.html\">Physics</a><a class=\"card\" href=\"calc/index.html\">Calculus</a></div><p class=\"muted\">Private shared teacher resources. Course folders are populated by the local teacher tools.</p></div></body></html>"""


def build_course_placeholder(title: str) -> str:
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{escape(title)} Teacher Shared</title><style>body{{font-family:Arial,Helvetica,sans-serif;margin:40px;color:#173f6d}}a{{color:#173f6d}}</style></head><body><h1>{escape(title)} Teacher Shared</h1><p>This course folder is ready. Its planner will publish here when connected.</p><p><a href=\"../index.html\">Teacher Shared home</a></p></body></html>"""


def build_physics_library_index() -> str:
    units = "".join(
        f'<a class="unit" href="unit{u}/index.html">Unit {u}</a>' for u in range(1, 9)
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Physics Teacher Library</title><style>body{{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f4f6f8;color:#173f6d}}.wrap{{max-width:1000px;margin:40px auto;padding:0 18px}}h1{{background:#173f6d;color:white;padding:18px 20px;border-radius:14px}}.units{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}}.unit{{display:block;background:white;border:2px solid #d9c06d;border-radius:12px;padding:18px;text-align:center;text-decoration:none;color:#173f6d;font-weight:900}}.unit:hover{{background:#fff8df}}.back{{display:inline-block;margin-top:18px;color:#173f6d;font-weight:800;text-decoration:none;border:1px solid #d4b34e;border-radius:999px;padding:8px 13px;background:#fff}}</style></head><body><div class="wrap"><h1>Physics Teacher Library</h1><p>Choose a unit. Each unit page contains approved assessment collections plus direct links to the unit assessment plan and bank.</p><div class="units">{units}</div><a class="back" href="../index.html">Teacher Agenda</a></div></body></html>"""


def _approved_quick_checks(unit: int) -> str:
    entries = []
    if QUICK_CHECK_LIBRARY.is_file():
        try:
            data = json.loads(QUICK_CHECK_LIBRARY.read_text(encoding="utf-8"))
            entries = [e for e in data.get("entries", []) if int(e.get("unit", 0) or 0) == unit]
        except Exception:
            entries = []
    if not entries:
        return f'<p class="placeholder">No approved Unit {unit} Quick Checks are registered yet.</p>'
    entries.sort(key=lambda e: (str(e.get("section", "")), str(e.get("run_id", ""))))
    rows = []
    for e in entries:
        section = escape(str(e.get("section") or f"Unit {unit}"))
        html_rel = str(e.get("html") or "").lstrip("/")
        pdf_rel = str(e.get("pdf") or "").lstrip("/")
        links = []
        if html_rel:
            links.append(f'<a href="{PUBLIC_BASE}quick_check____htq5855/{escape(html_rel, quote=True)}" target="_blank" rel="noopener">HTML</a>')
        if pdf_rel:
            links.append(f'<a href="{PUBLIC_BASE}quick_check____htq5855/{escape(pdf_rel, quote=True)}" target="_blank" rel="noopener">PDF</a>')
        rows.append(f'<li><strong>{section} Quick Check</strong> — {" · ".join(links) if links else "registered"}</li>')
    return '<ul>' + ''.join(rows) + '</ul>'


def _performance_tasks(unit: int) -> str:
    rows = []
    for section in range(1, 6):
        tag = f"{unit}_{section}"
        student = rel_if_exists(f"performance_task___5134zrt/u{tag}_performance_task/u{tag}_performance_task.html")
        teacher = rel_if_exists(f"performance_task___5134zrt/u{tag}_performance_task/u{tag}_performance_task_teacher_guide.html")
        if not student and not teacher:
            continue
        links = []
        if student:
            links.append(f'<a href="{escape(student, quote=True)}" target="_blank" rel="noopener">Performance Task</a>')
        if teacher:
            links.append(f'<a href="{escape(teacher, quote=True)}" target="_blank" rel="noopener">Teacher Guide</a>')
        rows.append(f'<li><strong>{unit}.{section}</strong> — {" · ".join(links)}</li>')
    if not rows:
        return f'<p class="placeholder">No Unit {unit} performance tasks are published yet.</p>'
    return '<ul>' + ''.join(rows) + '</ul>'


def build_physics_unit_library(unit: int) -> str:
    unit_nav = "".join(
        f'<a class="unitnav{" active" if u == unit else ""}" href="../unit{u}/index.html">Unit {u}</a>'
        for u in range(1, 9)
    )
    assessment_plan = f'https://tnezki.github.io/physics/assessment_plans/unit{unit}_assessment_plan/unit{unit}_assessment_plan.html'
    bank_rel = f"banks/unit{unit}/unit{unit}.html"
    bank_public = rel_if_exists(bank_rel)
    bank_target = bank_public or "bank.html"
    direct_nav = ''.join([
        f'<a class="directnav" href="{assessment_plan}" target="_blank" rel="noopener">Unit {unit} Assessment Plan</a>',
        f'<a class="directnav" href="{escape(bank_target, quote=True)}" target="_blank" rel="noopener">Unit {unit} Bank</a>',
    ])
    quick_checks = _approved_quick_checks(unit)
    assessments = _secure_assessments(unit)
    perf = _performance_tasks(unit)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Physics Unit {unit} Teacher Library</title><style>body{{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f4f6f8;color:#173f6d}}.wrap{{max-width:1080px;margin:30px auto;padding:0 18px}}h1{{background:#173f6d;color:#fff;padding:18px 20px;border-radius:14px;margin-bottom:12px}}.unitbar,.directbar{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}}.unitnav,.directnav{{text-decoration:none;color:#173f6d;background:#fff;border:1px solid #d4b34e;border-radius:999px;padding:8px 12px;font-weight:800}}.unitnav.active{{background:#e4bf3f}}.directnav:hover,.unitnav:hover{{background:#fff8df}}.section{{background:#fff;border:1px solid #d9dee5;border-radius:14px;padding:18px;margin:14px 0;scroll-margin-top:16px}}.section h2{{margin:0 0 8px}}.section a{{color:#173f6d;font-weight:800}}.placeholder{{color:#667085}}ul{{margin:8px 0 0;padding-left:24px}}li{{margin:7px 0}}</style></head><body><div class="wrap"><h1>Physics Unit {unit} Teacher Library</h1><div class="unitbar">{unit_nav}</div><div class="directbar">{direct_nav}</div><section id="quick-checks" class="section"><h2>Approved Quick Checks</h2>{quick_checks}</section><section id="assessments" class="section"><h2>Approved Assessments</h2>{assessments}</section><section id="performance-tasks" class="section"><h2>Performance Tasks</h2>{perf}</section></div></body></html>"""

def ensure_teacher_shared_layout() -> None:
    migrate_secure_summatives()
    SHARED_ROOT.mkdir(parents=True, exist_ok=True)
    SHARED_PHYSICS_ROOT.mkdir(parents=True, exist_ok=True)
    atomic_write_text(SHARED_ROOT / "index.html", build_teacher_shared_home())
    for folder, title in (("algebra", "Algebra 1"), ("calc", "Calculus")):
        target = SHARED_ROOT / folder / "index.html"
        if not target.is_file():
            atomic_write_text(target, build_course_placeholder(title))

    # Reuse the same shared teacher agenda styling as Algebra when available.
    physics_assets = SHARED_PHYSICS_ROOT / "assets"
    physics_assets.mkdir(parents=True, exist_ok=True)
    source_css = SHARED_ROOT / "algebra" / "assets" / "teacher_portal.css"
    target_css = physics_assets / "teacher_portal.css"
    if source_css.is_file():
        target_css.write_bytes(source_css.read_bytes())
    elif not target_css.is_file():
        atomic_write_text(target_css, "body{font-family:Arial,Helvetica,sans-serif;margin:0;color:#1f2937}.wrapper{width:min(1500px,calc(100% - 28px));margin:14px auto}.titlebar,.section-title{background:#173f6d;color:#fff;padding:12px}.resource-block{background:#fff9e9;border:1px solid #e0bd4f;padding:12px}.resource-row{display:flex;flex-wrap:wrap;gap:8px}.resource-row a{border:1px solid #e0bd4f;border-radius:999px;padding:7px 12px;color:#173f6d;text-decoration:none}.calendar-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;table-layout:fixed;min-width:1050px}th,td{border:1px solid #cfd4da;padding:7px}.week-head th{background:#173f6d;color:#fff}.teacher-row td{background:#e8eff7}.teacher-link{color:#25486f;font-weight:800;text-decoration:none}")

    data_dir = SHARED_PHYSICS_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    if not PRIVATE_ARTIFACTS.is_file():
        atomic_write_text(PRIVATE_ARTIFACTS, json.dumps({"schema": "teacher-private-artifacts/1.0", "entries": []}, indent=2) + "\n")

    library = SHARED_PHYSICS_ROOT / "library"
    atomic_write_text(library / "index.html", build_physics_library_index())
    for unit in range(1, 9):
        unit_dir = library / f"unit{unit}"
        atomic_write_text(unit_dir / "index.html", build_physics_unit_library(unit))
        if not (PHYSICS_ROOT / f"banks/unit{unit}/unit{unit}.html").is_file():
            atomic_write_text(unit_dir / "bank.html", f'<!doctype html><meta charset="utf-8"><title>Physics Unit {unit} Bank</title><style>body{{font-family:Arial,Helvetica,sans-serif;max-width:800px;margin:48px auto;padding:0 20px;color:#173f6d}}h1{{background:#173f6d;color:white;padding:18px;border-radius:12px}}</style><h1>Physics Unit {unit} Bank</h1><p>This unit bank has not been built yet.</p><p><a href="index.html">Back to Unit {unit} Teacher Library</a></p>')

    assess = SHARED_PHYSICS_ROOT / "assessments"
    assess.mkdir(parents=True, exist_ok=True)
    atomic_write_text(assess / "index.html", '<!doctype html><meta http-equiv="refresh" content="0; url=../library/index.html"><p><a href="../library/index.html">Open Physics Teacher Library</a></p>')
    quick = assess / "quick_checks" / "index.html"
    quick.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(quick, '<!doctype html><meta http-equiv="refresh" content="0; url=../../library/index.html"><p><a href="../../library/index.html">Open Physics Teacher Library</a></p>')

def compact_text(parts) -> str:
    return re.sub(r"\s+", " ", "".join(parts)).strip()


class AgendaParser(HTMLParser):
    """Parse the existing static agenda so Planner can adopt it once."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.capture = False
        self.tbody_classes = []
        self.rows = []
        self.current_row = None
        self.current_cell = None
        self.current_anchor = None
        self.weeks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tbody":
            classes = attrs.get("class", "").split()
            # Ignore the featured duplicate current week; capture ALL WEEKS blocks only.
            if "week-block" in classes and (
                "previous-week" in classes or "all-current-week" in classes
            ):
                self.capture = True
                self.tbody_classes = classes
                self.rows = []
        elif self.capture and tag == "tr":
            self.current_row = []
        elif self.capture and tag in {"th", "td"} and self.current_row is not None:
            self.current_cell = {
                "tag": tag,
                "text_parts": [],
                "href": None,
                "classes": attrs.get("class", "").split(),
                "colspan": int(attrs.get("colspan", "1") or 1),
            }
        elif self.capture and tag == "a" and self.current_cell is not None:
            self.current_anchor = attrs.get("href")
            if self.current_cell["href"] is None:
                self.current_cell["href"] = self.current_anchor

    def handle_data(self, data):
        if self.capture and self.current_cell is not None:
            self.current_cell["text_parts"].append(data)

    def handle_endtag(self, tag):
        if not self.capture:
            return
        if tag == "a":
            self.current_anchor = None
        elif tag in {"th", "td"} and self.current_cell is not None:
            self.current_cell["text"] = compact_text(self.current_cell.pop("text_parts"))
            if self.current_anchor and not self.current_cell["href"]:
                self.current_cell["href"] = self.current_anchor
            self.current_row.append(self.current_cell)
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None
        elif tag == "tbody":
            self.weeks.append({"classes": list(self.tbody_classes), "rows": self.rows})
            self.capture = False
            self.tbody_classes = []
            self.rows = []


def academic_iso(mmdd: str) -> str | None:
    m = re.search(r"(\d{1,2})/(\d{1,2})", mmdd or "")
    if not m:
        return None
    month, day = map(int, m.groups())
    year = 2026 if month >= 7 else 2027
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def section_code(title: str) -> str | None:
    m = re.match(r"\s*(\d+)\.(\d+)", title or "")
    if not m:
        return None
    return f"{int(m.group(1))}.{int(m.group(2))}"


def section_sort_key(title: str):
    code = section_code(title)
    if not code:
        return (999, 999, title)
    u, s = code.split(".")
    return (int(u), int(s), title)


def parse_welcome_day(url: str | None) -> int | None:
    if not url:
        return None
    m = re.search(r"/(\d+)_(\d+)_(\d+)_welcome\.html(?:\?|$)", url)
    if not m:
        return None
    return int(m.group(3))


def normalize_control(label: str) -> str:
    low = (label or "").strip().casefold()
    if not low:
        return "Regular Day"
    if "summative" in low:
        return "Regular Day"
    if "sub" in low:
        return "Sub Assignment"
    if "nwea" in low or "testing" in low or low == "test":
        return "Testing"
    if "ok2say" in low or "assembly" in low:
        return "Assembly Schedule"
    if low in {"p.d.", "pd", "p.d"} or "professional development" in low:
        return "P.D."
    if "half" in low or "1/2" in low:
        return "1/2 Day"
    if "snow" in low:
        return "Snow Day"
    if "no school" in low:
        return "No School"
    if "break" in low or "labor day" in low or "holiday" in low:
        return "Break"
    return label if label in DAY_CONTROLS else "Regular Day"


def default_slots(day_number: int | None) -> list[str]:
    if day_number == 1:
        return ["Warm Up", "Notes", "Practice Set", "", ""]
    if day_number == 2:
        return ["Warm Up", "Investigation", "Practice Set", "Extra Practice", ""]
    if day_number == 3:
        return ["Warm Up", "Activity", "Practice Set", "Extra Practice", "Quick Check"]
    return ["", "", "", "", ""]


def expand_row(row: list[dict]) -> list[dict]:
    cells = []
    for cell in row:
        span = max(1, int(cell.get("colspan", 1) or 1))
        for _ in range(span):
            cells.append(cell)
    while len(cells) < 5:
        cells.append({"text": "", "href": None, "classes": [], "tag": "td", "colspan": 1})
    return cells[:5]


def item_kind(label: str, first: bool) -> str:
    if not first:
        return ""
    low = (label or "").casefold()
    if any(t in low for t in ("labor day", "p.d", "no school", "holiday", "break", "snow")):
        return "holiday"
    return "lesson"


def parse_existing_agenda(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Student agenda not found: {path}")
    parser = AgendaParser()
    parser.feed(path.read_text(encoding="utf-8"))
    if not parser.weeks:
        raise RuntimeError("Could not find ALL WEEKS blocks in the current student agenda.")

    days = []
    current_week_index = 0
    section_occurrence = {}

    for week_index, week in enumerate(parser.weeks):
        if "all-current-week" in week["classes"]:
            current_week_index = week_index
        rows = week["rows"]
        if not rows:
            continue
        header = expand_row(rows[0])
        data_rows = [expand_row(r) for r in rows[1:] if r]
        for col in range(5):
            date_label = header[col].get("text", "")
            iso = academic_iso(date_label)
            if not iso:
                iso = f"2026-01-{col+1:02d}"
            d = datetime.strptime(iso, "%Y-%m-%d").date()
            items = []
            for row in data_rows:
                cell = row[col]
                label = cell.get("text", "").strip()
                if not label or label == "No published agenda items.":
                    continue
                items.append({
                    "label": label,
                    "url": cell.get("href"),
                    "kind": item_kind(label, not items),
                })

            first = items[0] if items else None
            section = first["label"] if first and section_code(first["label"]) else ""
            control = "Regular Day" if section else normalize_control(first["label"] if first else "")
            day_number = parse_welcome_day(first.get("url") if first else None)
            if section:
                code = section_code(section)
                if day_number is None:
                    count = section_occurrence.get(code, 0) + 1
                    section_occurrence[code] = count
                    day_number = ((count - 1) % 3) + 1
                else:
                    section_occurrence[code] = max(section_occurrence.get(code, 0), day_number)

            past = week_index < current_week_index
            if week_index <= current_week_index:
                slots = [i["label"] for i in items[1:6]]
                slots += [""] * (5 - len(slots))
            elif section and control == "Regular Day":
                slots = default_slots(day_number)
            else:
                slots = ["", "", "", "", ""]

            days.append({
                "week_index": week_index,
                "date": iso,
                "dow": d.strftime("%A"),
                "display_date": f"{d.month}/{d.day}",
                "control": control,
                "section": section,
                "day_number": day_number or 0,
                "student_slots": slots,
                "custom_slots": [{"label": "", "url": ""} for _ in range(5)],
                "legacy_items": items if past else [],
                "locked_past": False,
                # Existing non-regular dates were already reflected in the old sheet plan.
                "shift_applied": control in SHIFTING_CONTROLS,
                "assessment_unit": 0,
            })

    return {
        "schema": "physics-planner-state/0.4",
        "school_year": "2026-2027",
        "current_week_index": current_week_index,
        "days": days,
        "created_from": "agenda/index.html",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def load_quick_check_map() -> dict[str, str]:
    if not QUICK_CHECK_LIBRARY.is_file():
        return {}
    try:
        data = json.loads(QUICK_CHECK_LIBRARY.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for entry in data.get("entries", []):
        section = str(entry.get("section") or "").strip()
        rel = str(entry.get("html") or "").strip()
        if section and rel:
            out[section] = f"{PUBLIC_BASE}quick_check____htq5855/{rel}"
    return out


def rel_if_exists(relative: str) -> str | None:
    path = PHYSICS_ROOT / relative
    if path.is_file():
        return PUBLIC_BASE + quote(relative, safe="/._-")
    return None


def normalize_custom_url(raw: str) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if re.match(r"^https?://", value, flags=re.I):
        return value
    if value.startswith(("/", "./", "../")):
        return value
    if re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/|$)", value):
        return "https://" + value
    return None


def resource_url(resource: str, section_title: str, day_number: int = 0) -> str | None:
    code = section_code(section_title)
    if not code:
        return None
    unit_s, sec_s = code.split(".")
    unit, sec = int(unit_s), int(sec_s)
    tag = f"{unit}_{sec}"
    if resource == "Warm Up":
        return rel_if_exists(f"warmups/unit_{unit}_warmups/unit_{unit}_warmups.html")
    if resource == "Notes":
        return rel_if_exists(f"notes/u{tag}_notes/u{tag}_notes.html")
    if resource == "Investigation":
        return rel_if_exists(f"investigations/u{tag}_investigation/u{tag}_investigation.html")
    if resource == "Activity":
        return rel_if_exists(f"activities/u{tag}_act1/u{tag}_act1.html")
    if resource == "Demo":
        return rel_if_exists(f"demo/u{tag}_demo/u{tag}_demo.html")
    if resource == "Performance Task":
        return rel_if_exists(f"performance_task___5134zrt/u{tag}_performance_task/u{tag}_performance_task.html")
    if resource == "Practice Set":
        return rel_if_exists(f"practice_sets/practice_sets_{tag}/practice_set_{tag}.html")
    if resource == "Extra Practice":
        return rel_if_exists(f"practice_sets/practice_sets_{tag}/extra_practice_{tag}.html")
    if resource == "Review":
        return rel_if_exists(f"reviews/review{unit}/review_{unit}.html")
    if resource == "Quick Check":
        # Student agenda intentionally displays Quick Check without a link.
        return None
    return None


def welcome_url(section_title: str, day_number: int) -> str | None:
    code = section_code(section_title)
    if not code or day_number not in {1, 2, 3}:
        return None
    unit_s, sec_s = code.split(".")
    relative = f"misc/welcomes/slides/{int(unit_s)}_{int(sec_s)}_{day_number}_welcome.html"
    return rel_if_exists(relative)


def teacher_links(section_title: str, student_slots: list[str]) -> list[dict]:
    code = section_code(section_title)
    if not code:
        return []
    unit_s, sec_s = code.split(".")
    tag = f"{int(unit_s)}_{int(sec_s)}"
    links = []

    def add(label: str, relative: str):
        url = rel_if_exists(relative)
        if url and not any(x["url"] == url for x in links):
            links.append({"label": label, "url": url})

    if "Notes" in student_slots:
        add("Notes Teacher Guide", f"notes/u{tag}_notes/u{tag}_notes_teacher.html")
    if "Investigation" in student_slots:
        add(
            "Investigation Teacher Guide",
            f"investigations/u{tag}_investigation/u{tag}_investigation_teacher_guide.html",
        )
    if "Demo" in student_slots:
        add(
            "Demo Teacher Guide",
            f"demo/u{tag}_demo/u{tag}_demo_teacher_guide.html",
        )
    if "Performance Task" in student_slots:
        add(
            "Performance Task Teacher Guide",
            f"performance_task___5134zrt/u{tag}_performance_task/u{tag}_performance_task_teacher_guide.html",
        )
    return links


def load_private_artifacts() -> list[dict]:
    if not PRIVATE_ARTIFACTS.is_file():
        return []
    try:
        data = json.loads(PRIVATE_ARTIFACTS.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = []
    for raw in data.get("entries", []):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        rel = str(item.get("path") or "").strip().lstrip("/")
        external = str(item.get("url") or "").strip()
        if rel:
            local = (SHARED_PHYSICS_ROOT / rel).resolve()
            try:
                local.relative_to(SHARED_PHYSICS_ROOT.resolve())
            except ValueError:
                continue
            if not local.is_file():
                continue
            encoded = quote(rel, safe="/._-")
            item["planner_url"] = f"/shared/physics/{encoded}"
            item["shared_url"] = encoded
        elif external:
            item["planner_url"] = external
            item["shared_url"] = external
        else:
            continue
        entries.append(item)
    return entries


def private_links_for_section(code: str) -> list[dict]:
    out = []
    for item in load_private_artifacts():
        if str(item.get("section") or "").strip() != code:
            continue
        label = str(item.get("label") or "Teacher Resource").strip()
        out.append({
            "label": label,
            "planner_url": item["planner_url"],
            "shared_url": item["shared_url"],
            "role": str(item.get("role") or "Teacher").strip() or "Teacher",
        })
    return out


def private_summative_links(unit: int) -> list[dict]:
    out = []
    valid_kinds = {
        "summative_assessment",
        "summative_answer_key",
        "summative_teacher_guide",
    }
    for item in load_private_artifacts():
        kind = str(item.get("kind") or "").strip().casefold()
        try:
            item_unit = int(item.get("unit"))
        except Exception:
            continue
        if item_unit != unit or kind not in valid_kinds:
            continue
        label = str(item.get("label") or "Summative Assessment").strip()
        default_role = "Assessment" if kind == "summative_assessment" else "Teacher"
        out.append({
            "label": label,
            "planner_url": item["planner_url"],
            "shared_url": item["shared_url"],
            "role": str(item.get("role") or default_role).strip() or default_role,
        })
    return out


def build_registry(state: dict) -> dict:
    sections = sorted(
        {d.get("section", "") for d in state.get("days", []) if section_code(d.get("section", ""))},
        key=section_sort_key,
    )
    units = sorted({int(section_code(s).split(".")[0]) for s in sections if section_code(s)})
    registry = {
        "sections": sections,
        "resources": {},
        "teacher": {},
        "welcome": {},
        "shared": {"section": {}, "summative": {}},
    }
    for section in sections:
        registry["resources"][section] = {
            r: resource_url(r, section) for r in STUDENT_RESOURCE_OPTIONS if r
        }
        registry["teacher"][section] = {}
        for resource in ["Notes", "Investigation", "Demo", "Performance Task", "Quick Check"]:
            entries = teacher_links(section, [resource])
            registry["teacher"][section][resource] = entries[0] if entries else None
        registry["welcome"][section] = {
            str(n): welcome_url(section, n) for n in (1, 2, 3)
        }
        code = section_code(section)
        registry["shared"]["section"][code] = [
            {"label": e["label"], "url": e["planner_url"], "role": e["role"]}
            for e in private_links_for_section(code)
        ]
    for unit in units:
        registry["shared"]["summative"][str(unit)] = [
            {"label": e["label"], "url": e["planner_url"], "role": e["role"]}
            for e in private_summative_links(unit)
        ]
    return registry


def apply_manual_current_state(state: dict) -> None:
    days = state.get("days", [])
    if not days:
        state["current_week_index"] = 0
        return
    valid_weeks = sorted({int(d.get("week_index", 0)) for d in days})
    try:
        chosen = int(state.get("current_week_index", valid_weeks[0]))
    except Exception:
        chosen = valid_weeks[0]
    if chosen not in valid_weeks:
        chosen = valid_weeks[0]
    state["current_week_index"] = chosen
    state["schema"] = "physics-planner-state/0.4"
    for idx, d in enumerate(days):
        # Every week remains editable. Current week controls highlighting/publishing, not locks.
        d["locked_past"] = False
        d.setdefault("shift_applied", False)
        d.setdefault("assessment_unit", 0)
        # Migrate the short-lived Summative/Remove-Blank experiment into the simpler model.
        if d.get("control") == "Summative Assessment":
            unit = 0
            try:
                unit = int(d.get("assessment_unit") or 0)
            except Exception:
                unit = 0
            if not unit:
                for prior in reversed(days[:idx]):
                    code = section_code(str(prior.get("section") or ""))
                    if code:
                        unit = int(code.split(".")[0])
                        break
            d["control"] = "Regular Day"
            d["section"] = str(d.get("section") or "").strip() or (f"Unit {unit} Test" if unit else "Unit Test")
            d["day_number"] = 0
            d["student_slots"] = ["", "", "", "", ""]
            d["shift_applied"] = False
        elif d.get("control") == "Insert Blank Day" and d.get("shift_applied"):
            # The shift was already applied by the previous Planner version. Keep the blank date,
            # but reset the dropdown so selecting Insert again is always a fresh action.
            d["control"] = "Regular Day"
            d["shift_applied"] = False
        custom = d.get("custom_slots")
        if not isinstance(custom, list):
            custom = []
        normalized = []
        for i in range(5):
            item = custom[i] if i < len(custom) and isinstance(custom[i], dict) else {}
            normalized.append({
                "label": str(item.get("label") or ""),
                "url": str(item.get("url") or ""),
            })
        d["custom_slots"] = normalized


LAST_WEEK_REPAIR_ID = "2026-09-21-sheet-repair-v1"
UNIT_TEST_LABELS_ID = "unit-transition-test-labels-v1"


def apply_known_state_repairs(state: dict) -> bool:
    """One-time repair for the sparse 9/21 week imported from the old static agenda.

    The old Google Sheet had the selected items shown below, but the first Planner
    import only captured a few of them. Repair only the exact sparse pattern so
    later teacher edits are never overwritten.
    """
    migrations = state.get("migrations")
    if not isinstance(migrations, list):
        migrations = []
        state["migrations"] = migrations
    if LAST_WEEK_REPAIR_ID in migrations:
        return False

    by_date = {
        str(d.get("date") or ""): d
        for d in state.get("days", [])
        if isinstance(d, dict)
    }
    required = ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25"]
    if not all(x in by_date for x in required):
        return False

    d21, d22, d23, d24, d25 = (by_date[x] for x in required)
    sparse_import = (
        str(d21.get("control") or "") == "P.D."
        and str(d22.get("control") or "") == "Sub Assignment"
        and not str(d22.get("section") or "").strip()
        and not str(d23.get("section") or "").strip()
        and section_code(str(d24.get("section") or "")) == "1.2"
        and not str(d25.get("section") or "").strip()
    )
    if not sparse_import:
        return False

    def set_day(day: dict, *, control: str, section: str, day_number: int, slots: list[str]):
        day["control"] = control
        day["section"] = section
        day["day_number"] = day_number
        day["student_slots"] = list(slots)
        day["custom_slots"] = [{"label": "", "url": ""} for _ in range(5)]
        day["locked_past"] = False
        day["shift_applied"] = control in SHIFTING_CONTROLS
        day["assessment_unit"] = 0

    # These are the checked/selected items from the 9/21-9/25 legacy sheet.
    set_day(d22, control="Sub Assignment", section="1.2: I/O & Functions", day_number=1,
            slots=["", "", "", "", ""])
    set_day(d23, control="Regular Day", section="1.2: I/O & Functions", day_number=2,
            slots=["Warm Up", "Activity", "Practice Set", "", ""])
    set_day(d24, control="Regular Day", section="1.2: I/O & Functions", day_number=3,
            slots=["Warm Up", "Activity", "Practice Set", "Extra Practice", ""])
    set_day(d25, control="Regular Day", section="1.3: Fn Families", day_number=1,
            slots=["Warm Up", "Notes", "Practice Set", "", ""])

    migrations.append(LAST_WEEK_REPAIR_ID)
    return True


def apply_unit_test_labels(state: dict) -> bool:
    """Fill the planned blank day between units with `Unit N Test`.

    This is a one-time planner migration. It does not create a new day and it
    does not shift instruction. It only labels an already-empty Regular Day
    that sits between the last section of one unit and the first section of the
    next unit. Existing teacher-entered content is never overwritten.
    """
    migrations = state.get("migrations")
    if not isinstance(migrations, list):
        migrations = []
        state["migrations"] = migrations
    if UNIT_TEST_LABELS_ID in migrations:
        return False

    days = state.get("days", [])
    changed = False

    def unit_of(day: dict) -> int:
        code = section_code(str(day.get("section") or ""))
        if not code:
            return 0
        return int(code.split(".", 1)[0])

    instructional = [(i, unit_of(day)) for i, day in enumerate(days) if unit_of(day)]
    for pos in range(len(instructional) - 1):
        left_i, left_unit = instructional[pos]
        right_i, right_unit = instructional[pos + 1]
        if right_unit <= left_unit:
            continue
        # Only a true unit transition gets a test label. Choose the first empty
        # Regular Day between the units, exactly matching the calendar pattern
        # used for Unit 1 in the Planner.
        for j in range(left_i + 1, right_i):
            day = days[j]
            if str(day.get("control") or "Regular Day") != "Regular Day":
                continue
            if str(day.get("section") or "").strip():
                continue
            if any(str(x or "").strip() for x in day.get("student_slots", [])):
                continue
            day["section"] = f"Unit {left_unit} Test"
            day["day_number"] = 0
            day["student_slots"] = ["", "", "", "", ""]
            day["custom_slots"] = [{"label": "", "url": ""} for _ in range(5)]
            day["assessment_unit"] = left_unit
            day["locked_past"] = False
            day["shift_applied"] = False
            changed = True
            break

    migrations.append(UNIT_TEST_LABELS_ID)
    return changed


def validate_state(state: dict) -> None:
    if not isinstance(state, dict) or not isinstance(state.get("days"), list):
        raise ValueError("Planner state must contain a days list.")
    for i, d in enumerate(state["days"]):
        if not isinstance(d, dict):
            raise ValueError(f"days[{i}] must be an object")
        try:
            datetime.strptime(str(d.get("date")), "%Y-%m-%d")
        except Exception as exc:
            raise ValueError(f"days[{i}] has invalid date") from exc
        slots = d.get("student_slots")
        if not isinstance(slots, list) or len(slots) != 5:
            raise ValueError(f"days[{i}] must have exactly 5 student_slots")
        for value in slots:
            if value not in STUDENT_RESOURCE_OPTIONS:
                raise ValueError(f"days[{i}] has unsupported resource: {value}")
        custom = d.get("custom_slots", [])
        if not isinstance(custom, list) or len(custom) != 5:
            raise ValueError(f"days[{i}] must have exactly 5 custom_slots")
        for ci, item in enumerate(custom):
            if not isinstance(item, dict):
                raise ValueError(f"days[{i}].custom_slots[{ci}] must be an object")
            if not isinstance(item.get("label", ""), str) or not isinstance(item.get("url", ""), str):
                raise ValueError(f"days[{i}].custom_slots[{ci}] must contain string label/url")
        control = d.get("control", "Regular Day")
        if control not in DAY_CONTROLS:
            raise ValueError(f"days[{i}] has unsupported control: {control}")
        if d.get("assessment_unit") not in (None, "", 0):
            try:
                int(d.get("assessment_unit"))
            except Exception as exc:
                raise ValueError(f"days[{i}] has invalid assessment_unit") from exc


def get_state() -> dict:
    if STATE_PATH.is_file():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            apply_manual_current_state(state)
            repaired = apply_unit_test_labels(state)
            apply_manual_current_state(state)
            validate_state(state)
            if repaired:
                state["updated_at"] = datetime.now().isoformat(timespec="seconds")
                atomic_write_text(STATE_PATH, json.dumps(state, indent=2) + "\n")
            return state
        except Exception as exc:
            print(f"Planner state could not be loaded; rebuilding from agenda: {exc}")
    state = parse_existing_agenda(AGENDA_PATH)
    apply_manual_current_state(state)
    apply_unit_test_labels(state)
    apply_manual_current_state(state)
    atomic_write_text(STATE_PATH, json.dumps(state, indent=2) + "\n")
    return state


def save_state(state: dict) -> dict:
    apply_manual_current_state(state)
    validate_state(state)
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    atomic_write_text(STATE_PATH, json.dumps(state, indent=2) + "\n")
    return state


def day_items(day: dict, past: bool = False) -> list[dict]:
    # Published output always comes from the editable Planner state, including past weeks.
    items = []
    control = day.get("control", "Regular Day")
    section = day.get("section", "")
    if control in BLOCKED_CONTROLS:
        kind = "holiday" if control in {"Snow Day", "P.D.", "Break", "No School"} else "lesson"
        items.append({"label": control, "url": None, "kind": kind})
        return items

    if section:
        items.append({
            "label": section,
            "url": welcome_url(section, int(day.get("day_number", 0) or 0)),
            "kind": "lesson",
        })
    if control != "Regular Day":
        items.append({"label": control, "url": None, "kind": ""})

    custom_slots = day.get("custom_slots") or []
    for idx, resource in enumerate(day.get("student_slots", [])):
        if not resource:
            continue
        if resource == "Custom Item":
            custom = custom_slots[idx] if idx < len(custom_slots) and isinstance(custom_slots[idx], dict) else {}
            label = str(custom.get("label") or "Custom Item").strip() or "Custom Item"
            url = normalize_custom_url(custom.get("url"))
            items.append({"label": label, "url": url, "kind": ""})
            continue
        items.append({
            "label": resource,
            "url": resource_url(resource, section, int(day.get("day_number", 0) or 0)),
            "kind": "",
        })
    return items


def render_item(item: dict, class_name: str = "cal-link") -> str:
    label = escape(str(item.get("label") or ""))
    kind = item.get("kind") or ""
    classes = class_name + (f" {kind}" if kind else "")
    url = item.get("url")
    if url:
        return (
            f'<a class="{classes}" href="{escape(url, quote=True)}" '
            f'target="_blank" rel="noopener">{label}</a>'
        )
    return f'<span class="{classes} no-link">{label}</span>'


def render_week(state: dict, week_index: int, display_class: str, featured: bool = False) -> str:
    days = [d for d in state["days"] if int(d.get("week_index", 0)) == week_index]
    if len(days) < 5:
        return ""
    if featured:
        header_cells = "".join(
            f"<th><span class='dow'>{escape(d['dow'])}</span><span class='date'>{escape(d['display_date'])}</span></th>"
            for d in days[:5]
        )
    else:
        header_cells = "".join(
            f"<th><div class='date'>{escape(d['display_date'])}</div></th>" for d in days[:5]
        )

    past = week_index < int(state.get("current_week_index", 0))
    per_day = [day_items(d, past) for d in days[:5]]
    row_count = max((len(x) for x in per_day), default=0)
    rows = []
    for ri in range(row_count):
        cells = []
        for items in per_day:
            cells.append(f"<td>{render_item(items[ri])}</td>" if ri < len(items) else "<td></td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    if not rows:
        rows.append('<tr><td colspan="5" class="empty-week">No published agenda items.</td></tr>')
    return (
        f'<tbody class="week-block {display_class}"><tr class="week-head">'
        f'{header_cells}</tr>{"".join(rows)}</tbody>'
    )


def build_student_agenda(state: dict) -> str:
    apply_manual_current_state(state)
    current = int(state.get("current_week_index", 0))
    week_indices = sorted({int(d.get("week_index", 0)) for d in state.get("days", [])})
    featured = render_week(state, current, "current-week", featured=True)
    all_weeks = []
    for wi in week_indices:
        cls = "all-current-week" if wi == current else "previous-week"
        all_weeks.append(render_week(state, wi, cls, featured=False))

    student_links = [
        ("Overview", "https://docs.google.com/document/d/1rrToxZ84-VGe-75JeIofcH6FXqdCFiE-MNlwDZNvMs4/edit?usp=sharing"),
        ("Practice Builder", "https://tnezki.github.io/physics/practice_builder___p7r4x/student_practice_builder.html"),
        ("Textbook", "https://tnezki.github.io/textbooks/physics/index.html"),
        ("Formula Sheet", "https://tnezki.github.io/physics/misc/formula_sheet.html"),
        ("Vernier", "https://videoanalysis.app/"),
        ("Vernier Hints", "https://docs.google.com/document/d/1GihYf2MAXI7G2eIRL6x_J330focOVzB3dFdayrFiMR0/edit?usp=sharing"),
        ("Printables", "https://tnezki.github.io/algebra/misc/printables/aaagallery_index.html"),
        ("Upload Spot", "https://drive.google.com/drive/folders/1wxxAxIxJ9yU5goiVNriIVpmiEJmE7SX2?usp=drive_link"),
        ("Desmos", "https://www.desmos.com/calculator"),
        ("PhET", "https://phet.colorado.edu/en/simulations/filter?subjects=physics"),
        ("oPhysics", "https://ophysics.com/index.html"),
        ("Walter F", "https://www.walter-fendt.de/html5/phen/"),
        ("Falsted", "https://www.falstad.com//mathphysics.html"),
        ("Lewin Videos", "https://www.youtube.com/channel/UCiEHVhv0SBMpP75JbzJShqw"),
        ("Hewitt Videos", "https://conceptual.academy/"),
    ]
    resources = "\n".join(
        f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{escape(label)}</a>'
        for label, url in student_links
    )
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Physics Agenda 2026-2027</title>
<style>
:root{{--navy:#173f6d;--gold:#e0bd4f;--gold-light:#fff0b8;--current-row-a:#fffaf0;--current-row-b:#fff1bd;--ink:#1f2937;--muted:#64748b;--lesson:#fff0b8;--link:#173f6d}}
*{{box-sizing:border-box}} body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#fff;color:var(--ink)}}
.wrapper{{width:min(980px,calc(100% - 24px));margin:18px auto 40px}} .titlebar{{background:var(--navy);color:#fff;padding:7px 11px;border-radius:10px 10px 0 0;text-align:center}}
.titlebar h1{{margin:0;font-size:.88rem;font-weight:800}} .titlebar .small{{font-size:1em;font-weight:600}}
.resources{{border:1px solid var(--gold);border-top:0;padding:12px 14px 13px;display:flex;flex-wrap:wrap;justify-content:center;align-items:center;text-align:center;gap:8px;background:#fff9e9}}
.resources a{{text-decoration:none;color:var(--navy);background:#fff;border:1px solid var(--gold);border-radius:999px;padding:7px 11px;font-size:.88rem;font-weight:700}}
.resources a:hover,.resources a:focus-visible{{background:var(--gold-light);border-color:var(--navy)}} .calendar-wrap{{overflow-x:auto;border:1px solid #c8b675;border-top:0}}
table{{border-collapse:collapse;width:100%;max-width:100%;min-width:0;table-layout:fixed}} th,td{{border-right:1px solid #cfd4da;border-bottom:1px solid #cfd4da;text-align:center;vertical-align:middle}} tr>*:last-child{{border-right:0}}
.week-head th{{width:20%;padding:7px 5px}} .dow{{font-size:.82rem;font-weight:800}} .date{{margin-top:2px;font-size:.76rem;font-weight:700}} td{{padding:4px 5px;background:#fff;height:32px}}
.cal-link{{display:block;width:100%;text-decoration:none;color:var(--link);font-size:.82rem;font-weight:650;padding:4px;border-radius:5px;overflow-wrap:anywhere}} a.cal-link:hover,a.cal-link:focus-visible{{background:#fff4c7}}
.cal-link.lesson{{background:var(--lesson);border:1px solid #e1c86d;font-weight:800;color:var(--navy)}} .cal-link.holiday{{background:#f6edcf;color:#475569;font-weight:800}} .no-link{{cursor:default}} .empty-week{{color:var(--muted);font-size:.8rem;padding:10px}}
.current-week .week-head th{{background:var(--navy);color:#fff;text-align:left;padding:7px 6px}} .current-week .dow{{display:inline;font-size:.86rem;font-weight:850}} .current-week .date{{display:inline;margin:0 0 0 6px;font-size:.86rem;font-weight:900;color:#fff}}
.current-week td{{padding:0;height:40px;background:var(--current-row-a)}} .current-week tr:nth-child(odd):not(.week-head) td{{background:var(--current-row-b)}} .current-week .cal-link{{display:flex;align-items:center;justify-content:center;min-height:40px;padding:7px 4px;font-size:.90rem;font-weight:750;line-height:1.15}}
.current-week .cal-link.lesson{{background:rgba(255,255,255,.45);border:1px solid #dbc36d;color:var(--navy);font-size:.96rem;font-weight:900}}
.previous-weeks-divider td{{background:var(--navy)!important;color:#fff;font-size:.96rem;font-weight:800;padding:9px 7px}}
.all-current-week .week-head th{{background:var(--gold);color:var(--navy);border-top:5px solid var(--navy);text-align:left;padding-left:9px}} .all-current-week .week-head th .date{{color:var(--navy);font-size:.9rem;font-weight:900}}
.all-current-week tr td{{background:var(--current-row-a)!important;border-color:#d8c77f}} .all-current-week tr:nth-child(even) td{{background:var(--current-row-b)!important}} .all-current-week .cal-link.lesson{{background:#fff6d5;border:1px solid #dbc36d;color:var(--navy);font-weight:900}}
.previous-week .week-head th{{background:#3f4650;color:#fff;border-top:5px solid #20242a;text-align:left;padding-left:9px}} .previous-week .week-head th .date{{color:#e5e7eb}} .previous-week tr td{{background:#fff!important;border-color:#cfd4da}} .previous-week tr:nth-child(even) td{{background:#f3f4f6!important}} .previous-week .cal-link.lesson{{background:#e5e7eb;border:1px solid #c7ccd1;color:#2f3740}} .previous-week .cal-link.holiday{{background:#eceff2;color:#4b5563}}
.updated{{text-align:center;color:var(--muted);font-size:.76rem;padding-top:8px}} @media(max-width:700px){{.wrapper{{width:100%;margin:0}}.titlebar{{border-radius:0}}.resources{{justify-content:center;padding:10px}}.resources a{{font-size:.8rem;padding:6px 9px}}}}
</style>
</head>
<body>
<div class="wrapper">
<header class="titlebar"><h1>Physics <span class="small">– Agenda 2026-2027</span></h1></header>
<nav class="resources" aria-label="Student resources">{resources}</nav>
<div class="calendar-wrap"><table aria-label="Physics student agenda">{featured}<tbody class="previous-weeks-divider"><tr><td colspan="5">ALL WEEKS</td></tr></tbody>{''.join(all_weeks)}</table></div>
<div class="updated">Planner updated {escape(stamp)}</div>
</div>
</body>
</html>'''


def visible_resource_labels(day: dict, past: bool = False) -> list[str]:
    return [str(x) for x in day.get("student_slots", []) if x and x != "Custom Item"]


def infer_unit_for_day(state: dict, day: dict) -> int:
    try:
        unit = int(day.get("assessment_unit") or 0)
        if unit:
            return unit
    except Exception:
        pass
    code = section_code(str(day.get("section") or ""))
    if code:
        return int(code.split(".")[0])
    days = state.get("days", [])
    try:
        idx = days.index(day)
    except ValueError:
        idx = -1
    for i in range(idx - 1, -1, -1):
        code = section_code(str(days[i].get("section") or ""))
        if code:
            return int(code.split(".")[0])
    return 0


def teacher_links_for_day(state: dict, day: dict, shared_mode: bool = False) -> list[dict]:
    past = int(day.get("week_index", 0)) < int(state.get("current_week_index", 0))
    links = []

    def add(label: str, url: str | None, role: str = "Teacher"):
        if not url or any(x["url"] == url for x in links):
            return
        links.append({"label": label, "url": url, "role": role})

    section = str(day.get("section") or "")
    labels = visible_resource_labels(day, past)
    if re.search(r"\b(?:unit\s*\d+\s*)?(?:test|exam|assessment)\b", section, re.I):
        unit = infer_unit_for_day(state, day) or 1
        target = f"library/unit{unit}/index.html#assessments"
        add(
            "Approved Assessments",
            target if shared_mode else f"/shared/physics/{target}",
            "Assessment",
        )
    if section_code(section):
        for entry in teacher_links(section, labels):
            add(entry["label"], entry["url"], "Teacher")
        if "Quick Check" in labels:
            unit = infer_unit_for_day(state, day) or 1
            target = f"library/unit{unit}/index.html#quick-checks"
            add(
                "Approved Quick Checks",
                target if shared_mode else f"/shared/physics/{target}",
                "Assessment",
            )
        code = section_code(section)
        for entry in private_links_for_section(code):
            add(
                entry["label"],
                entry["shared_url"] if shared_mode else entry["planner_url"],
                entry["role"],
            )
    return links[:3]


def render_teacher_link(item: dict) -> str:
    role = escape(str(item.get("role") or "Teacher"))
    label = escape(str(item.get("label") or "Teacher Resource"))
    url = escape(str(item.get("url") or ""), quote=True)
    return (
        f'<span class="teacher-label">{role}</span>'
        f'<a class="teacher-link" href="{url}" target="_blank" rel="noopener">{label} ↗</a>'
    )


def render_teacher_week(state: dict, week_index: int, display_class: str, featured: bool = False) -> str:
    days = [d for d in state["days"] if int(d.get("week_index", 0)) == week_index][:5]
    if len(days) < 5:
        return ""
    if featured:
        header = "".join(
            f"<th>{escape(d['dow'])}<span class='date'>{escape(d['display_date'])}</span></th>"
            for d in days
        )
    else:
        header = "".join(
            f"<th><span class='date'>{escape(d['display_date'])}</span></th>" for d in days
        )
    past = week_index < int(state.get("current_week_index", 0))
    per_day = [day_items(d, past) for d in days]
    row_count = max((len(items) for items in per_day), default=0)
    rows = []
    for ri in range(row_count):
        cells = []
        for items in per_day:
            cells.append(
                f"<td>{render_item(items[ri], 'item')}</td>" if ri < len(items) else "<td></td>"
            )
        row_class = "lesson-row" if ri == 0 else ("student-row alt" if ri % 2 == 1 else "student-row")
        rows.append(f'<tr class="{row_class}">' + "".join(cells) + "</tr>")
    for row in range(3):
        cells = []
        for d in days:
            links = teacher_links_for_day(state, d, shared_mode=True)
            cells.append(
                f"<td>{render_teacher_link(links[row]) if row < len(links) else ''}</td>"
            )
        rows.append('<tr class="teacher-row">' + "".join(cells) + "</tr>")
    return (
        f'<tbody class="week-block {display_class}"><tr class="week-head">'
        f'{header}</tr>{"".join(rows)}</tbody>'
    )


def current_unit_for_state(state: dict) -> int:
    current = int(state.get("current_week_index", 0))
    units = []
    for day in state.get("days", []):
        if int(day.get("week_index", 0)) != current:
            continue
        unit = infer_unit_for_day(state, day)
        if unit:
            units.append(unit)
    return max(units) if units else 1


def build_teacher_agenda(state: dict) -> str:
    apply_manual_current_state(state)
    current = int(state.get("current_week_index", 0))
    week_indices = sorted({int(d.get("week_index", 0)) for d in state.get("days", [])})
    featured = render_teacher_week(state, current, "current-week", featured=True)
    previous_candidates = [wi for wi in week_indices if wi < current]
    previous = previous_candidates[-1] if previous_candidates else None
    previous_featured = (
        render_teacher_week(state, previous, "previous-week", featured=True)
        if previous is not None else ""
    )
    all_weeks = [
        render_teacher_week(
            state,
            wi,
            "all-current-week" if wi == current else "previous-week",
            featured=False,
        )
        for wi in week_indices
    ]
    student_links = [
        ("Overview", "https://docs.google.com/document/d/1rrToxZ84-VGe-75JeIofcH6FXqdCFiE-MNlwDZNvMs4/edit?usp=sharing"),
        ("Practice Builder", "https://tnezki.github.io/physics/practice_builder___p7r4x/student_practice_builder.html"),
        ("Textbook", "https://tnezki.github.io/textbooks/physics/index.html"),
        ("Formula Sheet", "https://tnezki.github.io/physics/misc/formula_sheet.html"),
        ("Vernier", "https://videoanalysis.app/"),
        ("Vernier Hints", "https://docs.google.com/document/d/1GihYf2MAXI7G2eIRL6x_J330focOVzB3dFdayrFiMR0/edit?usp=sharing"),
        ("Printables", "https://tnezki.github.io/algebra/misc/printables/aaagallery_index.html"),
        ("Upload Spot", "https://drive.google.com/drive/folders/1wxxAxIxJ9yU5goiVNriIVpmiEJmE7SX2?usp=drive_link"),
        ("Desmos", "https://www.desmos.com/calculator"),
        ("PhET", "https://phet.colorado.edu/en/simulations/filter?subjects=physics"),
        ("oPhysics", "https://ophysics.com/index.html"),
        ("Walter F", "https://www.walter-fendt.de/html5/phen/"),
        ("Falsted", "https://www.falstad.com//mathphysics.html"),
        ("Lewin Videos", "https://www.youtube.com/channel/UCiEHVhv0SBMpP75JbzJShqw"),
        ("Hewitt Videos", "https://conceptual.academy/"),
    ]
    current_unit = current_unit_for_state(state)
    unit_library = f"library/unit{current_unit}/index.html"
    teacher_links_top = [
        ("Teacher Library", unit_library),
        ("Activity Structures", "https://docs.google.com/document/d/18imPwnYQjblasMS8x97DjKeNDjWNKTnOa3iBoTwCYVA/edit?usp=sharing"),
        ("Reflections", "https://docs.google.com/document/d/1pooMLzaO0D9wKbjEwmE7E_9OpiI-qSssz9Vnv9PqQPU/edit?usp=drive_link"),
        ("Welcomes", "https://tnezki.github.io/physics/misc/welcomes/welcome.html"),
        ("Student Agenda", "https://tnezki.github.io/physics/agenda/index.html"),
    ]

    def nav(items):
        return "".join(
            f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{escape(label)}</a>'
            for label, url in items
        )

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Physics Shared Teacher Agenda</title>
<link rel="stylesheet" href="assets/teacher_portal.css">
</head>
<body>
<div class="wrapper">
<header class="titlebar"><h1>Physics - Shared Teacher Agenda</h1></header>
<section class="resource-block">
<p class="resource-label">Student Resources</p><div class="resource-row">{nav(student_links)}</div>
<p class="resource-label">Shared Teacher Resources</p><div class="resource-row">{nav(teacher_links_top)}</div>
</section>
<div class="notice">Read-only co-teacher view generated from the local Planner. Current and previous week are pinned at the top; ALL WEEKS remains below for reference.</div>
<div class="section-title">CURRENT WEEK - TEACHER VIEW</div>
<div class="calendar-wrap"><table aria-label="Current teacher agenda">{featured}</table></div>
{('<div class="section-title">PREVIOUS WEEK - TEACHER VIEW</div><div class="calendar-wrap"><table aria-label="Previous teacher agenda">' + previous_featured + '</table></div>') if previous_featured else ''}
<div class="section-title">ALL WEEKS</div>
<div class="calendar-wrap"><table aria-label="All teacher agenda weeks">{''.join(all_weeks)}</table></div>
<div class="footer">Planner published {escape(stamp)}</div>
</div>
</body>
</html>'''


def bootstrap_payload() -> dict:
    state = get_state()
    return {
        "state": state,
        "registry": build_registry(state),
        "options": {"resources": STUDENT_RESOURCE_OPTIONS, "controls": EDITOR_DAY_CONTROLS},
    }


class PlannerHandler(SimpleHTTPRequestHandler):
    server_version = "PhysicsPlanner/0.3"

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

    def _json(self, status: int, payload: dict):
        raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > 2_000_000:
            raise ValueError("Invalid request body length")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _serve_shared_file(self, url_path: str):
        rel = unquote(url_path[len("/shared/"):]).lstrip("/")
        target = (SHARED_ROOT / rel).resolve()
        target.relative_to(SHARED_ROOT.resolve())
        if not target.is_file():
            self.send_error(404, "Shared teacher file not found")
            return
        raw = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _serve_physics_file(self, url_path: str):
        rel = unquote(url_path[len("/physics/"):]).lstrip("/")
        target = (PHYSICS_ROOT / rel).resolve()
        target.relative_to(PHYSICS_ROOT.resolve())
        if not target.is_file():
            self.send_error(404, "Physics file not found")
            return
        raw = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/version":
            self._json(200, {"ok": True, "version": PLANNER_VERSION})
            return
        if path == "/api/bootstrap":
            try:
                self._json(200, bootstrap_payload())
            except Exception as exc:
                self._json(500, {"ok": False, "error": str(exc)})
            return
        if path == "/api/state":
            try:
                self._json(200, {"ok": True, "state": get_state()})
            except Exception as exc:
                self._json(500, {"ok": False, "error": str(exc)})
            return
        if path in {"/shared/physics", "/shared/physics/", "/shared/physics/index.html"}:
            try:
                raw = build_teacher_agenda(get_state()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                self.send_error(500, f"Could not build co-teacher preview: {exc}")
            return
        if path in {"/shared", "/shared/", "/shared/index.html"}:
            try:
                self._serve_shared_file("/shared/index.html")
            except Exception:
                self.send_error(404, "Teacher Shared home not found")
            return
        if path.startswith("/shared/"):
            try:
                self._serve_shared_file(path)
            except Exception:
                self.send_error(404, "Shared teacher file not found")
            return
        if path.startswith("/physics/"):
            try:
                self._serve_physics_file(path)
            except Exception:
                self.send_error(404, "Physics file not found")
            return
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/planner/")
            self.end_headers()
            return
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            state = payload.get("state") if isinstance(payload, dict) else None
            if path == "/api/git-pull-all":
                result = git_pull_all()
                self._json(200 if result.get("ok") else 409, result)
                return
            if path == "/api/git-push-all":
                result = git_push_all()
                self._json(200 if result.get("ok") else 409, result)
                return
            if path == "/api/save":
                state = save_state(state)
                self._json(
                    200,
                    {"ok": True, "state": state, "message": "Planner state saved."},
                )
                return
            if path in {"/api/update-agenda", "/api/publish"}:
                state = save_state(state)
                ensure_teacher_shared_layout()
                atomic_write_text(AGENDA_PATH, build_student_agenda(state))
                atomic_write_text(SHARED_INDEX, build_teacher_agenda(state))
                self._json(
                    200,
                    {
                        "ok": True,
                        "state": state,
                        "message": (
                            "Planner saved; Student Agenda and Co-Teacher Agenda updated locally. "
                            "Review both repositories in GitHub Desktop, then push when ready."
                        ),
                        "student_path": str(AGENDA_PATH),
                        "teacher_path": str(SHARED_INDEX),
                    },
                )
                return
            self._json(404, {"ok": False, "error": "Unknown API endpoint"})
        except Exception as exc:
            self._json(400, {"ok": False, "error": str(exc)})


def main():
    ensure_teacher_shared_layout()
    if not PHYSICS_ROOT.is_dir():
        raise SystemExit(f"Physics repository not found at {PHYSICS_ROOT}")
    if not AGENDA_PATH.is_file():
        raise SystemExit(f"Student agenda not found at {AGENDA_PATH}")

    handler = lambda *args, **kwargs: PlannerHandler(
        *args, directory=str(TEACHER_TOOLS_ROOT), **kwargs
    )
    server = ThreadingHTTPServer((HOST, PORT), handler)
    url = f"http://{HOST}:{PORT}/planner/"
    print(f"Physics Planner v{PLANNER_VERSION}")
    print("===============")
    print(f"Teacher Tools root: {TEACHER_TOOLS_ROOT}")
    print(f"Physics repo:        {PHYSICS_ROOT}")
    print(f"Teacher shared repo: {SHARED_ROOT}")
    print(f"Physics shared path: {SHARED_PHYSICS_ROOT}")
    print(f"Planner:             {url}")
    print("Press Control-C to stop.")
    if os.environ.get("PLANNER_NO_BROWSER") != "1":
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
