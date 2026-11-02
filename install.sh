#!/usr/bin/env bash
# Install the blog-voice skill and its always-loaded companion rule into one or more agent
# harnesses (claude-code, pi, codex, opencode), at user or project scope.
#
#   ./install.sh [--harness H]... [--scope user|project] [--project-root DIR]
#                [--link] [--templates] [--uninstall] [--dry-run]
#
# Harness layout:
#   claude-code  skill -> <base>/.claude/skills/blog-voice
#                rule  -> <base>/.claude/rules/BLOG_VOICE.md
#   pi|codex|opencode
#                skill -> <base>/.agents/skills/blog-voice   (shared; read by all three)
#                rule  -> managed block in the harness AGENTS.md:
#                           user:    pi ~/.pi/agent/AGENTS.md, codex ~/.codex/AGENTS.md,
#                                    opencode ~/.config/opencode/AGENTS.md
#                           project: <root>/AGENTS.md (shared)
# <base> is $HOME at user scope and the project root at project scope.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="blog-voice"
SRC_SKILL="$REPO_DIR/skills/$SKILL_NAME"
SRC_RULE="$SRC_SKILL/protocols/BLOG_VOICE.md"
BEGIN_MARK="<!-- BEGIN blog-voice rule (managed by blog-voice/install.sh; edits are overwritten) -->"
END_MARK="<!-- END blog-voice rule -->"

harnesses=()
scope="user"
project_root=""
link=0
templates=0
uninstall=0
dry=0

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --harness) harnesses+=("$2"); shift 2 ;;
    --scope) scope="$2"; shift 2 ;;
    --project-root) project_root="$2"; shift 2 ;;
    --link) link=1; shift ;;
    --templates) templates=1; shift ;;
    --uninstall) uninstall=1; shift ;;
    --dry-run) dry=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "unknown argument: $1" >&2; usage 2 ;;
  esac
done

[ ${#harnesses[@]} -eq 0 ] && harnesses=(claude-code)
expanded=()
for h in "${harnesses[@]}"; do
  case "$h" in
    all) expanded+=(claude-code pi codex opencode) ;;
    claude-code|pi|codex|opencode) expanded+=("$h") ;;
    *) echo "unknown harness: $h (claude-code|pi|codex|opencode|all)" >&2; exit 2 ;;
  esac
done

case "$scope" in
  user) base="$HOME" ;;
  project)
    if [ -z "$project_root" ]; then
      project_root="$(git rev-parse --show-toplevel 2>/dev/null)" \
        || { echo "--scope project needs --project-root or a git working directory" >&2; exit 2; }
    fi
    base="$(cd "$project_root" && pwd)"
    [ "$base" = "$REPO_DIR" ] && { echo "refusing to install into the blog-voice source repo" >&2; exit 2; }
    ;;
  *) echo "--scope must be user or project" >&2; exit 2 ;;
esac

run() { if [ $dry -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

# Ordered, de-duplicated destination sets.
skill_dests=()
rule_files=()
block_files=()
# Bash 3.2-safe (macOS /bin/bash): no namerefs.
contains() { local v="$1" x; shift; for x in "$@"; do [ "$x" = "$v" ] && return 0; done; return 1; }
add_unique() { # array-name value
  case "$1" in
    skill_dests) contains "$2" "${skill_dests[@]+"${skill_dests[@]}"}" || skill_dests+=("$2") ;;
    rule_files) contains "$2" "${rule_files[@]+"${rule_files[@]}"}" || rule_files+=("$2") ;;
    block_files) contains "$2" "${block_files[@]+"${block_files[@]}"}" || block_files+=("$2") ;;
  esac
}
for h in "${expanded[@]}"; do
  if [ "$h" = "claude-code" ]; then
    add_unique skill_dests "$base/.claude/skills/$SKILL_NAME"
    add_unique rule_files "$base/.claude/rules/BLOG_VOICE.md"
  else
    add_unique skill_dests "$base/.agents/skills/$SKILL_NAME"
    if [ "$scope" = "project" ]; then
      add_unique block_files "$base/AGENTS.md"
    else
      case "$h" in
        pi) add_unique block_files "$HOME/.pi/agent/AGENTS.md" ;;
        codex) add_unique block_files "$HOME/.codex/AGENTS.md" ;;
        opencode) add_unique block_files "$HOME/.config/opencode/AGENTS.md" ;;
      esac
    fi
  fi
done

strip_block() { # file -> prints file without the managed block
  awk -v b="$BEGIN_MARK" -v e="$END_MARK" '
    $0 == b {skip=1; next}
    $0 == e {skip=0; next}
    !skip' "$1"
}

write_block() { # file
  local f="$1" tmp
  run mkdir -p "$(dirname "$f")"
  [ $dry -eq 1 ] && { echo "[dry-run] update managed block in $f"; return; }
  tmp="$(mktemp)"
  if [ -f "$f" ]; then strip_block "$f" | awk 'NF{n=NR} {l[NR]=$0} END{for(i=1;i<=n;i++)print l[i]}' > "$tmp"; fi
  {
    [ -s "$tmp" ] && { cat "$tmp"; echo; }
    echo "$BEGIN_MARK"
    cat "$SRC_RULE"
    echo "$END_MARK"
  } > "$tmp.new"
  mv -f "$tmp.new" "$f"; rm -f "$tmp"
}

remove_block() { # file
  local f="$1" tmp
  [ -f "$f" ] && grep -qF "$BEGIN_MARK" "$f" || return 0
  [ $dry -eq 1 ] && { echo "[dry-run] remove managed block from $f"; return; }
  tmp="$(mktemp)"
  strip_block "$f" | awk 'NF{n=NR} {l[NR]=$0} END{for(i=1;i<=n;i++)print l[i]}' > "$tmp"
  mv -f "$tmp" "$f"
}

install_skill() { # dest
  local d="$1"
  run mkdir -p "$(dirname "$d")"
  run rm -rf "$d"
  if [ $link -eq 1 ]; then
    run ln -s "$SRC_SKILL" "$d"
  else
    run cp -R "$SRC_SKILL" "$d"
    if [ $dry -eq 0 ]; then
      find "$d" \( -name __pycache__ -o -name .DS_Store \) -prune -exec rm -rf {} +
      # Stamp this copy's own location into the SKILL_DIR resolver.
      local esc="${d//\\/\\\\}"; esc="${esc//&/\\&}"; esc="${esc//|/\\|}"
      sed -i.bak "s|^SKILL_DIR_INSTALLED_AT=\"\"$|SKILL_DIR_INSTALLED_AT=\"$esc\"|" "$d/SKILL.md"
      rm -f "$d/SKILL.md.bak"
    fi
  fi
}

if [ $uninstall -eq 1 ]; then
  for d in "${skill_dests[@]}"; do echo "remove skill  $d"; run rm -rf "$d"; done
  for f in "${rule_files[@]+"${rule_files[@]}"}"; do echo "remove rule   $f"; run rm -f "$f"; done
  for f in "${block_files[@]+"${block_files[@]}"}"; do echo "remove block  $f"; remove_block "$f"; done
  exit 0
fi

for d in "${skill_dests[@]}"; do echo "skill  -> $d"; install_skill "$d"; done
for f in "${rule_files[@]+"${rule_files[@]}"}"; do
  echo "rule   -> $f"; run mkdir -p "$(dirname "$f")"; run cp -f "$SRC_RULE" "$f"
done
for f in "${block_files[@]+"${block_files[@]}"}"; do echo "block  -> $f"; write_block "$f"; done

if [ $templates -eq 1 ]; then
  if [ "$scope" != "project" ]; then
    echo "--templates applies only to --scope project; skipped" >&2
  else
    for t in VOICE.md AUDIENCE.md ILLUSTRATIONS.md; do
      if [ -e "$base/$t" ]; then echo "template $t exists; kept"
      else echo "template -> $base/$t"; run cp "$REPO_DIR/templates/$t" "$base/$t"; fi
    done
  fi
fi

command -v harper-cli >/dev/null 2>&1 || echo "note: harper-cli not found; grammar-check will be skipped (brew install harper)"
command -v uv >/dev/null 2>&1 || echo "note: uv not found; the skill's helper scripts need it"
