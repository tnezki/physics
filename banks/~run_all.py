import subprocess
import sys
from pathlib import Path

# ── CONFIGURE ───────────────────────────────────────────────────────────────
# Defaults to the folder this script lives in.
# Override to target a different folder:
#   TARGET_FOLDER = r"/Users/troynezki/Downloads/friday/algebra"
TARGET_FOLDER = Path(__file__).parent

# Skip this script itself so it doesn't run itself recursively.
SKIP = {Path(__file__).name}
# ────────────────────────────────────────────────────────────────────────────

py_files = sorted(
    p for p in Path(TARGET_FOLDER).rglob("*.py")  # recursive: all subfolders too
    if p.is_file() and p.name not in SKIP
)

if not py_files:
    print("No Python files found.")
    sys.exit()

print(f"Found {len(py_files)} script(s) in {Path(TARGET_FOLDER).resolve()}\n")

for py in py_files:
    print(f"{'═'*60}")
    print(f"  Running: {py.name}")
    print(f"{'═'*60}")
    result = subprocess.run(
        [sys.executable, str(py)],   # uses the same Python that's running this script
        cwd=str(py.parent)           # runs each script from its own folder
    )
    if result.returncode != 0:
        print(f"  ⚠ {py.name} exited with code {result.returncode}")
    print()

print("All scripts finished.")
