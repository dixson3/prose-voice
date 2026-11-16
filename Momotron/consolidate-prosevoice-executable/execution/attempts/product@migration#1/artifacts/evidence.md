# Evidence: migration step

## Checks

| Check | Result | Log |
| :-- | :-- | :-- |
| Migration preservation, conflicts and interrupted apply | 32 tests OK, exit 0 | `check-migration.log` |
| Full runtime regression | 142 tests OK, exit 0 (110 baseline + 32 new) | `check-full-suite.log` |
| Ruff over `skills/prosevoice` and `tests` | clean | `ruff.log` |
| Wheel build | succeeds; `prosevoice_lib/migration.py` included | `wheel-build.log` |

Baseline before this step: 110 tests OK (`baseline-tests.log`, `baseline-status.txt`). The legacy trees `skills/pv-preflight` and `skills/pv-prosevoice` are byte-unchanged (`git diff --quiet`). `final-status.txt` records the closing status: the new untracked items are `tests/fixtures/`, `tests/test_prosevoice_migration.py` and this attempt's artifacts. The operator-installed `.agents/`, `.claude/` and `skills-lock.json` were not touched.

## Changes

- `skills/prosevoice/scripts/prosevoice_lib/migration.py` (new) implements `prosevoice migrate`:
  - Scopes: `--scope project|user`, `--apply`, `--legacy-user-dir`, and `--user-dir` (user scope only). Preview is the default.
  - Strict validation of the legacy config: duplicate keys, unknown semantics and invalid values all block.
  - Translation to `schema_version: 1`. Relative paths into the legacy tree are remapped, paths into the legacy user directory map to the new user directory and are tracked as dependencies, and external references are retained and reported.
  - Byte-exact copies of the guides, policy files and `.gitignore`. Unknown files are listed as retained.
  - An essay inventory that handles nested duplicate stems. Cache-mode sidecars are copied to the new cache routes, with relative Markdown links, reference links and `Source:`/`Render:` fields rebased. Raw HTML and angle-bracket links block. Orphaned sidecars are retained and produce a warning. Other cache history is reported as skipped.
  - Rule switching for `PV-PROTOCOL.md` and `BLOG_VOICE.md` files and for `pv-protocol` and `blog-voice` blocks at the project, Claude, pi, Codex and OpenCode targets. Legacy content is recognized by SHA-256 against the five released protocol texts. The shared conservative block parser rejects malformed, nested, duplicate or overlapping blocks. A rule switch requires a `prosevoice` installation at the same target (`rules.rule_targets`).
  - Equivalence checks run through the shared resolver: `config.build_config` and `resolve_guidance(state_of=...)`, `policy.policy_sources`/`words_from_text`/`rules_from_text`, `essay.image_outcome`. They compare guide bytes, the policy union, the artifact mode and READY visual outcomes. Preview checks against staged bytes; apply re-checks on disk before activating rules.
  - A manifest at `<scope>/migrations/<id>/manifest.json` holding input hashes, before/after hashes per action, staged bytes and backups of replaced rules. Intent is recorded before each atomic replace, and rules are activated last.
  - Resume accepts completed writes only when they equal their recorded after hash. Pending writes resume from either their before or after state. Any other state blocks and names the file and the manifest path.
  - Recovery instructions are returned in `data.recovery`.
- Shared-layer refactors made so migration does not duplicate logic:
  - `config.build_config`, `config.text_state`, and a `state_of` parameter on `resolve_guidance`.
  - `policy.words_from_text` and `policy.rules_from_text`.
  - `essay.active_anchors` and `essay.image_outcome`.
- `cli.py` adds the `migrate` subcommand. It uses the common envelope: blocked → exit 1; invalid new config, usage errors and `--set` → exit 2.
- `tests/test_prosevoice_runtime.py` exempts `migration.py` from the legacy-name scan. Per `migration.md`, it is the only module allowed to read legacy identities.
- `tests/fixtures/legacy_rules/` holds the four released `PV-PROTOCOL.md` texts and `BLOG_VOICE.md`, extracted from git history.
- `tests/test_prosevoice_migration.py` (new, 32 tests) covers:
  - no-config projects, ordered and external guides, user-only and mixed fallback
  - user policy retained alongside project guides
  - cache and adjacent modes, duplicate nested stems, link rebasing, no-image choices
  - blank templates, custom ignores, retained unknown files
  - every released protocol version, and project and global rule targets (Claude file, project AGENTS.md, pi, Codex, OpenCode)
  - legacy remnants absorbed by an existing current block, unrelated AGENTS bytes including CRLF
  - differing and equal destinations, invalid, duplicate and unknown legacy config, invalid new config
  - modified, malformed, end-only, begin-only, duplicate, nested and stale blocks
  - symlink escapes, symlinked legacy guides as external references
  - ambiguous sidecars, unsupported links, missing installation, unmet user dependencies, usage errors
  - failure injection before a replacement, after a replacement but before the completion record, before rule activation and mid rule phase
  - an intervening edit, a changed input, no repeated manifests or backups on rerun
  - runtime ignoring retained legacy data before and after migration

  Preview and blocked runs assert that the whole fixture tree is unchanged.

## Interpretations for review

- **Missing visual decisions.** An essay with active anchors but no sidecar anywhere does not block migration. Its READY outcome was already blocked under the legacy layout and stays identically blocked, so no decision is lost; the equivalence report records it. Decisions that exist but cannot be mapped (a sidecar only in the other mode's location, or a symlinked or non-UTF-8 sidecar) do block, with the paths. If the contract intends any unresolved active anchor to block migration, this needs changing.
- **Migration manifests and Git.** Manifests live in `.prosevoice/migrations/`, outside the cache. Migration does not add an ignore rule for them, so operators may see them as untracked files. The integration docs should say whether to commit or ignore them.
- **No new cache ignore line.** Migration does not write a cache ignore line itself. It copies the legacy `.gitignore`, which legacy runtime created in cache mode. Ordinary artifact-producing commands still add the ignore line when needed.
- **Unrecognized protocol content.** Legacy rule recognition is limited to released texts: four `PV-PROTOCOL.md` versions and one `BLOG_VOICE.md`. Any other content blocks for manual review.
- **Not run against real data.** Migration was not run against any real operator project or user directory.
