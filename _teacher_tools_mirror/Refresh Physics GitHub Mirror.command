#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GITHUB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$GITHUB_ROOT/_physics_teacher_tools"
DEST="$GITHUB_ROOT/physics/_teacher_tools_mirror"
[ -d "$SOURCE" ] || { echo "ERROR: $SOURCE not found"; exit 1; }
[ -d "$GITHUB_ROOT/physics/.git" ] || { echo "ERROR: physics repo not found"; exit 1; }
mkdir -p "$DEST"
rsync -a --delete --exclude='.DS_Store' --exclude='__MACOSX/' --exclude='runtime/' --exclude='*.log' --exclude='*.pid' --exclude='*.tmp' --exclude='*.zip' --exclude='*.bak' --exclude='*.pyc' --exclude='__pycache__/' "$SOURCE/" "$DEST/"
cat > "$DEST/README.md" <<'EOF'
# Physics Teacher Tools Mirror
One-way diagnostic mirror of local `_physics_teacher_tools`. The local folder remains the executable source of truth. Real student data must never be mirrored; use only sanitized fixtures under `fixtures/`.
EOF
python3 - "$DEST" <<'PY2'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]); items=[]
for p in sorted(root.rglob('*')):
    if p.is_file() and p.name!='MIRROR_MANIFEST.json':
        b=p.read_bytes(); items.append({'path':p.relative_to(root).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
(root/'MIRROR_MANIFEST.json').write_text(json.dumps({'schema_version':1,'source':'_physics_teacher_tools','destination':'physics/_teacher_tools_mirror','file_count':len(items),'files':items},indent=2)+'
')
PY2
echo "Physics teacher-tools mirror refreshed. Next: GitHub Sync -> Commit + Push."
read -r -p "Press Return to close..." _
