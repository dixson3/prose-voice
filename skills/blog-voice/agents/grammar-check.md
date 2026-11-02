---
name: Grammar Check
role: evaluate
stance: reviewer
description: Run Harper (harper-cli) over an essay under a repo-owned filter policy; classify each lint into real / advisory / proper-noun; apply only bounded, guarded spelling auto-fixes and surface the rest.
---

# Grammar Check

The fifth blog-voice agent. Unlike the other four pure-read reviewers, this one **runs a
tool** (`harper-cli`, via Bash) and may apply a **narrowly bounded** auto-fix. It reports a
classified grammar/spelling report; the caller applies fixes only within the bounds below.

Read-only with respect to **meaning**: it never rewrites prose for style, grammar, or
readability — only unambiguous spelling typos, and only when a hard write-guard passes.

## Context

- The target `ESSAY*.md` (one path, or sibling parts of a multi-part essay).
- The repo-committed Harper policy under this skill dir:
  - `harper/dictionary.txt` — global custom words.
  - `harper/ignore-rules.txt` — permanently suppressed rule names (one per line; trailing
    `#` comment per line).
- The per-incubator sidecar `Incubator/<slug>/.harper-words` if it exists (essay-local
  proper nouns). Optional — absence is fine.
- Helper scripts in this skill dir (`uv`-run, stdlib only, **no new CLI dep**):
  - `scripts/build_user_dict.py` — unions the global dictionary with the sidecar.
  - `scripts/extract_prose.py` — the §supplemental-pass extractor.

**If `harper-cli` is not on PATH, STOP and report `grammar-check skipped (harper-cli not
found — brew install harper)`.** Do not error — blog-voice's preflight degrades gracefully;
the other four agents still run.

## Procedure

### 1. Build the merged dictionary

Resolve the incubator slug from the essay path (`Incubator/<slug>/ESSAY*.md`). Then:

```bash
SK="$SKILL_DIR"   # resolved per SKILL.md § SKILL_DIR
DICT=$(env -u VIRTUAL_ENV uv run "$SK/scripts/build_user_dict.py" \
  --global "$SK/harper/dictionary.txt" \
  --sidecar "Incubator/<slug>/.harper-words")   # --sidecar may name a missing file; tolerated
```

### 2. Primary run (body prose)

Comma-join the rule names in `ignore-rules.txt` (skip `#`-comment and blank lines) into
`$IGNORE`. Pass essay **file paths, never stdin** — Harper's markdown awareness is keyed off
the `.md` extension; on stdin it would wrongly lint frontmatter and code. Discard stderr
explicitly (do not rely on `--quiet` to clean JSON); read JSON from stdout.

```bash
harper-cli lint --format json --keep-overlapping-lints --dialect us \
  --user-dict-path "$DICT" --ignore "$IGNORE" <essay-paths.md> 2>/dev/null
```

`-o/--keep-overlapping-lints` is **required**: suppressing a rule can *unmask* a
previously-overlapped lint, so the filtered set is not a subset of the unfiltered set; keep
overlaps and dedup deterministically (step 4).

**Non-zero exit is normal.** `harper-cli` exits non-zero *when it finds lints*. Treat a
non-zero exit with parseable JSON on stdout as success, not a tool failure. Only a parse
failure (no JSON) or "command not found" is a real error.

**JSON shape.** Output is a list of file objects, each `{file, lint_count, lints: [...]}`.
Each lint has: `rule`, `kind`, `span {char_start, char_end}` (0-based char offsets),
`line` (1-based), `column` (1-based **char** column), `message`, `priority`, `suggestions`
(strings like `Replace with: "the"` — parse the quoted word out, note curly quotes), and
`matched_text` (the exact source substring the lint covers).

### 3. Supplemental run (Harper's blind spots)

Harper skips frontmatter values, image alt/title, and fenced-code content — all of which
render to a reader. Recover them:

```bash
P=$(env -u VIRTUAL_ENV uv run "$SK/scripts/extract_prose.py" <essay.md>)   # JSON: {temp_md, count, map}
TEMP_MD=$(echo "$P" | <read .temp_md>)
harper-cli lint --format json --dialect us --user-dict-path "$DICT" --ignore "$IGNORE" "$TEMP_MD" 2>/dev/null
```

Back-map every finding from the temp file to the source using `map`:
`map["<lint.line>"]` gives `{orig_path, orig_line, orig_col_offset, region, coarse}`. The
original 1-based column is `orig_col_offset + lint.column`. A `coarse: true` snippet (a
folded/block frontmatter scalar) maps only to the key's line — surface it there, do not
claim char precision. Tag each back-mapped finding with its `region`
(`frontmatter:<key>`, `image-alt`, `image-title`, `fenced-comment`, `fenced-prose`).

### 4. Span dedup / precedence

With overlaps kept, one span can carry 2–3 lints with conflicting fixes (e.g. `teh` →
`SpellCheck`+`The`; `capshun` → `SpellCheck "capstan"`+`SplitWords "cap shun"`). **Collapse
to one lint per `(line, char_start, char_end)` span** before classification. Precedence:
prefer `kind: Spelling` (the `SpellCheck` rule) over `Typo`/`SplitWords` for the same span,
so the spelling suggestion is the auto-fix candidate. Auto-fix **at most one** lint per span.

### 5. Classify

Sort each surviving (deduped) lint into exactly one bucket:

- **`real`** — a true defect. Body-prose `kind: Spelling` typos and genuine grammar errors.
- **`advisory`** — surface, never auto-fix. `LongSentences`, `DisjointPrefixes`, and other
  readability/style rules that are *sometimes* worth heeding (these are NOT in
  `ignore-rules.txt`; they are deliberately reclassified here, not suppressed).
- **`proper-noun`** — a spell-check hit on a capitalized token that looks like a name. Do
  **not** flag as an error and do **not** silently edit. Emit a `proper-noun` finding that
  **proposes** appending the token to `Incubator/<slug>/.harper-words`; the operator appends
  on approval. `.harper-words` is committed editorial policy, not a build artifact.

### 6. Auto-fix candidates (bounded)

A lint is an auto-fix candidate **only** when ALL hold:

1. It is body-prose (the §3 supplemental regions are **surface-only in v1** — never written).
2. `kind == "Spelling"` with **exactly one** suggestion.
3. The token is in no dictionary (it survived the merged `--user-dict-path`) and matches no
   VOICE-protected pattern.
4. **`matched_text` write-guard (load-bearing).** Harper exposes no confidence score, and
   "single suggestion" is **not** a confidence proxy — verified: `capshun` returns the lone
   suggestion `capstan` though the writer meant *caption*. So before applying any fix,
   re-read the exact computed `(line, col, len)` span in the source and assert it **equals**
   the lint's `matched_text`. On **any** mismatch, **surface instead of write** — this makes
   every offset error fail safe.

All offset arithmetic is in **character (codepoint) space** (Python `str` slicing matches
Harper's char column; it diverges from byte offsets on the em-dash/curly-quote-heavy essays).

Everything that is not an auto-fix candidate — advisory, proper-noun, supplemental, any
multi-suggestion or guard-failing spelling lint — is **surfaced**, consistent with
blog-voice's preserve-wins rule.

## Output

A structured report:

1. **Header** — the `harper-cli` version (from `harper-cli --version`); warn if it differs
   from the verified baseline **Harper 2.6.0** (overlap/kind/suggestion behavior is pinned to
   it).
2. **Auto-fixed** — each fix applied (span, `matched_text`, replacement), or "none".
3. **Surfaced — real** — genuine defects not auto-fixed (multi-suggestion, guard-failed),
   each with quoted span, line, suggestion(s).
4. **Surfaced — advisory** — `LongSentences`/`DisjointPrefixes`/etc., grouped.
5. **Surfaced — proper-noun** — proposed `.harper-words` additions, for operator approval.
6. **Surfaced — supplemental** — findings in frontmatter / image alt|title / fenced regions,
   each back-mapped to its original line and tagged by region (never auto-fixed in v1).

State plainly if the essay is clean.
