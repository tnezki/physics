import subprocess
import sys
from pathlib import Path

# ── VS CODE POLISH RUNNER ───────────────────────────────────────────────────
# Put this file in the curriculum folder you want to polish.
# Open THIS file in VS Code and press Run.
#
# It intentionally runs ONLY the curriculum polish script.
# The polish script automatically detects and runs the newest fix_mathjax_v*.py
# in the same folder first.
#
# This avoids the danger of a generic run_all.py accidentally rerunning
# generate_graphs.py or other Python utilities in the curriculum package.
# ─────────────────────────────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent

# Prefer the newest polish_curriculum_v*.py in this folder.
candidates = sorted(
    HERE.glob("polish_curriculum_v*.py"),
    key=lambda p: int(p.stem.rsplit("_v", 1)[1]) if "_v" in p.stem and p.stem.rsplit("_v", 1)[1].isdigit() else -1,
)

if not candidates:
    print("No polish_curriculum_v*.py found in this folder.")
    sys.exit(1)

polisher = candidates[-1]

print("=" * 72)
print(f"Running curriculum polish: {polisher.name}")
print(f"Target folder: {HERE}")
print("=" * 72)
print()

result = subprocess.run(
    [sys.executable, str(polisher)],
    cwd=str(HERE),
)

if result.returncode != 0:
    print()
    print(f"Polish exited with code {result.returncode}")
    sys.exit(result.returncode)

print()
print("Polish finished.")
