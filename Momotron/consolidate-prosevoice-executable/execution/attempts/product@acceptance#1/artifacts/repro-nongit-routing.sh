#!/bin/sh
# Reproduces the non-Git essay routing difference between HEAD helpers and the consolidated pv.
# Usage: repro-nongit-routing.sh <blog-voice-repo>
set -u
REPO=$1
OLD=$(mktemp -d); git -C "$REPO" archive HEAD skills | tar -x -C "$OLD"
W=$(mktemp -d); mkdir -p "$W/essays" "$W/elsewhere" "$W/home" "$W/xdg"
printf -- '---\ntitle: X\n---\n\nBody <!-- illus:a1 -->\n' > "$W/essays/e.md"
export HOME="$W/home" XDG_CONFIG_HOME="$W/xdg"
cd "$W/elsewhere"
echo "OLD ready_preconditions.py (expect exit 3, sidecar under essays/.prose-voice/cache):"
uv run -q --script "$OLD/skills/pv-prosevoice/scripts/ready_preconditions.py" "$W/essays/e.md" --json; echo "exit $?"
echo "NEW pv ready (observed exit 2, essay-outside-project):"
env -u VIRTUAL_ENV uv run -q --script "$REPO/skills/prosevoice/scripts/prosevoice.py" ready "$W/essays/e.md"; echo "exit $?"
cd "$W"
echo "NEW pv artifacts from non-Git parent (observed <W>/.prosevoice/cache/essays/, old <W>/essays/.prose-voice/cache/):"
env -u VIRTUAL_ENV uv run -q --script "$REPO/skills/prosevoice/scripts/prosevoice.py" artifacts essays/e.md --kind illustrations; echo "exit $?"
