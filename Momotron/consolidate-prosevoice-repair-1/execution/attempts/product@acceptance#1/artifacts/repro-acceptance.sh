#!/bin/sh
# Independent acceptance reproduction for B1. Usage: repro-acceptance.sh <repo>
set -u
REPO=$1
W=$(mktemp -d /tmp/pvacc.XXXXXX); W=$(cd "$W" && pwd -P)
export HOME="$W/home" XDG_CONFIG_HOME="$W/xdg" GIT_CEILING_DIRECTORIES="$W"
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$W/unrelated" "$W/parent/essays"
printf 'Intro\n<!-- illus:fig1 -->\nMore.\n' > "$W/parent/essays/e.md"
PV="uv run --quiet $REPO/skills/prosevoice/scripts/prosevoice.py"
run() { echo "\$ (cwd=$1) pv $2"; (cd "$1" && eval "$PV $2"); echo "exit=$?"; echo; }
echo "W=$W"
run "$W/unrelated" "ready $W/parent/essays/e.md"
run "$W/unrelated" "artifacts $W/parent/essays/e.md --kind illustrations"
run "$W/parent" "artifacts $W/parent/essays/e.md --kind illustrations"
run "$W/parent" "ready essays/e.md"
mkdir -p "$W/parent/essays/.prosevoice/cache"
printf '## illus:fig1\nselected: fig1Svg\n' > "$W/parent/essays/.prosevoice/cache/e.illustrations.md"
echo "--- selected sidecar written beside essay"
run "$W/unrelated" "ready $W/parent/essays/e.md"
run "$W/parent" "ready essays/e.md"
echo "--- explicit project (outside / inside / missing)"
run "$W/unrelated" "artifacts $W/parent/essays/e.md --project $W/unrelated --kind draft"
run "$W/unrelated" "artifacts $W/parent/essays/e.md --project $W/parent --kind draft"
run "$W/unrelated" "artifacts $W/parent/essays/e.md --project $W/nope --kind draft"
echo "--- git-backed essay routes to its git root"
mkdir -p "$W/gitproj/a/b"; git -C "$W/gitproj" init -q; printf 'Hi.\n' > "$W/gitproj/a/b/g.md"
run "$W/unrelated" "artifacts $W/gitproj/a/b/g.md --kind draft"
echo "--- --set guidance anchored to invocation cwd"
run "$W/unrelated" "config $W/parent/essays/e.md --set 'guidance.VOICE.md=[\"v.md\"]'"
run "$W/unrelated" "check $W/parent/essays/e.md --set 'guidance.VOICE.md=[\"v.md\"]'"
echo "--- not-yet-created essay directory"
run "$W/unrelated" "artifacts $W/parent/new/x/d.md --apply"
ls -la "$W/parent/new/x/.prosevoice" "$W/parent/new/x/.prosevoice/cache"; cat "$W/parent/new/x/.prosevoice/.gitignore"
echo "--- stray .prosevoice dirs (should be none outside essays/ and new/x/):"
find "$W" -name .prosevoice -type d | grep -v '/home/' 
