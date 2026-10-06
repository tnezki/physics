#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GITHUB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$GITHUB_ROOT/_physics_teacher_tools"
DEST="$GITHUB_ROOT/physics/_teacher_tools_mirror"

if [ ! -d "$SOURCE" ]; then
  echo "ERROR: Physics teacher tools folder not found: $SOURCE"
  exit 1
fi

if [ ! -d "$GITHUB_ROOT/physics/.git" ]; then
  echo "ERROR: physics Git repository not found: $GITHUB_ROOT/physics"
  exit 1
fi

mkdir -p "$DEST"

rsync -a --delete \
  --exclude='.DS_Store' \
  --exclude='__MACOSX/' \
  --exclude='runtime/' \
  --exclude='*.log' \
  --exclude='*.pid' \
  --exclude='*.tmp' \
  --exclude='*.zip' \
  --exclude='*.bak' \
  --exclude='*.pyc' \
  --exclude='__pycache__/' \
  "$SOURCE/" "$DEST/"

cat > "$DEST/README.md" <<'EOF_README'
# Physics Teacher Tools Mirror

One-way diagnostic mirror of local `_physics_teacher_tools`.

- The local `_physics_teacher_tools` folder remains the executable source of truth.
- Do not edit files in this mirror directly.
- Real student data must never be mirrored.
- Use only sanitized fixture data under `fixtures/` when student-shaped records are needed for testing.
- Refresh this mirror with `_physics_teacher_tools/Refresh Physics GitHub Mirror.command`, then use GitHub Sync when ready.
EOF_README

python3 - "$DEST" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

root = Path(sys.argv[1])
items = []
for path in sorted(root.rglob('*')):
    if not path.is_file() or path.name == 'MIRROR_MANIFEST.json':
        continue
    data = path.read_bytes()
    items.append({
        'path': path.relative_to(root).as_posix(),
        'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
    })

payload = {
    'schema_version': 1,
    'source': '_physics_teacher_tools',
    'destination': 'physics/_teacher_tools_mirror',
    'file_count': len(items),
    'files': items,
}
(root / 'MIRROR_MANIFEST.json').write_text(
    json.dumps(payload, indent=2) + '\n',
    encoding='utf-8',
)
PY

echo
echo "Physics teacher-tools mirror refreshed."
echo "Source:     $SOURCE"
echo "Git mirror: $DEST"
echo
echo "Next: GitHub Sync -> Commit + Push."
echo
read -r -p "Press Return to close..." _
