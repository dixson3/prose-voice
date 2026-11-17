# Integration evidence (product:integration#4)

## Starting state

Attempts #1 and #2 were interrupted and #3 never ran (adapter model selector). Retained from #2 and inspected here: the two legacy source skill trees (`skills/pv-prosevoice`, `skills/pv-preflight`) were already deleted in the working tree; root `README.md` and `AGENTS.md` were rewritten for the single skill; `skills/prosevoice/README.md`, `SKILL.md` and agents already used the `pv` CLI; `essay.py` carried an untested `READY_LIMITATIONS` field. `tests/check_distribution.py` was absent. `CLAUDE.md` is still the `@AGENTS.md` include wrapper.

## Changes in this attempt

- `tests/check_distribution.py` (new, stdlib PEP 723, executable). This is one focused script with three surfaces, each run in a temp dir with isolated `HOME`/`XDG_CONFIG_HOME`, a minimal environment (no harness or virtualenv variables), `UV_PYTHON_DOWNLOADS=never`, and the developer's existing uv/npm caches only:
  - **wheel:** `uv build --wheel` into a temp directory. Asserts that the archive contains all 19 required resources under `prosevoice_lib/_skill/` (SKILL, protocol, 12 agents, 2 Harper policy files, 3 templates), the console entry point, and no legacy files. Installs into an isolated `uv venv` (`--offline`) and runs `prosevoice --help`/`version` from an unrelated cwd: version must equal `VERSION`, resources must be `packaged` from the venv, and resource bytes must equal the source. It then runs the shared runtime exercise.
  - **copy:** copies only `skills/prosevoice` and runs its launcher with `uv run --script`. Asserts `skill_root` is the copy and that no sibling exists, then runs the shared runtime exercise.
  - **Shared runtime exercise** (both surfaces), with `--project` from an unrelated cwd:
    - config: explicit selection, builtin provenance, and an unknown `--set` key giving exit 2;
    - init: seeds bytes equal to the bundled templates, adds the `/cache/` ignore, and is idempotent;
    - guides: an unfilled template is blocked; filled example guides resolve and illustrations stay optional;
    - policy: unions bundled, project and `.harper-words` policy from this installation, with no legacy sources;
    - artifacts: all 12 kinds route to the nested cache, and adjacent mode works;
    - READY: plain is clear (0); multipart `[needs-source]` blocks with its line (1); an active anchor blocks (1) until a `no-image` sidecar at the resolved path clears it (0); a missing part errors (2);
    - premise: 16-hex fingerprint;
    - every envelope's status/exit pairing is checked.
  - **install:** runs `npx -y skills add <absolute repo> -s prosevoice -a claude-code -a pi -y` in a scratch Git repo containing a pre-existing `AGENTS.md`, then checks:
    - installed paths: `.agents/skills/prosevoice`, with `.claude/skills/prosevoice` resolving to it; only `prosevoice` exists in either directory; the installed tree is byte-identical to the source skill; nothing was written under the isolated HOME;
    - the `SKILL_DIR` block, extracted from `SKILL.md` and run with `sh`, finds the install;
    - the installed helper:
      - `check` is blocked before setup;
      - `init` plus filled guides make `resolve` succeed;
      - `rule` preview plans exactly the Claude rule file and the `AGENTS.md` block, and writes nothing;
      - `rule --apply` writes the protocol and keeps the original `AGENTS.md` bytes as a prefix;
      - a second apply is idempotent;
      - `check` then reports ready with all rules `current`;
      - READY first reports `needs-source` and `visual-unresolved`, then clears after resolution.
  - Exit codes: 0 when everything passes, 1 on any failed command or assertion (stdout/stderr and payload are printed), and 2 when only unverified. A missing tool or a network-pattern failure counts as unverified, never as a pass. Unexpected exceptions count as failures.
- `tests/test_prosevoice_runtime.py`: added `test_ready_reports_mechanical_limitations_in_every_outcome` for the retained `data.limitations` field (clear and blocked outcomes).
- `essay.py`: parenthesized the implicit string concatenations in `READY_LIMITATIONS` (ruff ISC004; text unchanged).
- `README.md` command reference and `SKILL.md` READY step: document `data.limitations`.

## Documentation review against implementation

Checked against `cli.py`, `config.py` and `rules.py`:
- the 13 commands and their exact options (`--project`, `--set`, init `--scope/--illustrations`, artifacts `--kind/--apply`, rule `--remove/--apply`, policy `--sidecar/--user-dict/--user-ignore/--bundled-dictionary/--bundled-ignore/--out`, lint `--dialect`, extract `--out-md`, migrate `--scope/--apply/--legacy-user-dir/--user-dir`);
- the envelope and the 0/1/2 exit codes;
- the config schema, precedence and per-filename replacement;
- path anchors, XDG rules and project selection;
- the 12 kinds and the cache/adjacent layout;
- additive Harper policy;
- rule targets and dedup, and the managed-block markers;
- migration preview/apply, user dependencies (`user-dependency-unmet`), retained legacy data, the manifest/backups location, the policy that migration does not git-ignore `migrations/`, and recovery steps;
- installation and `npx skills` validation instructions (README and AGENTS).

Template headings and the `pv-template: unfilled` marker are untouched, and the examples are generic. Prose uses one line per paragraph.

## Obsolete-reference sweep

`legacy-reference-sweep.txt` covers tracked and untracked live product files, excluding Momotron, `.agents/`, `.claude/`, `skills-lock.json` and `.beads/`. Every remaining match is allowed:
- migration code, tests and fixtures;
- negative assertions in the tests and the checker's `LEGACY` tuple;
- the `--legacy-user-dir` help text;
- historical "ported from" docstrings in `essay.py`/`policy.py`;
- the old-script→command mapping in the skill README;
- the README/AGENTS migration documentation;
- `premise_fingerprint:` matches, which are a live sidecar frontmatter field, not the retired script.

No runtime fallback to legacy paths exists outside `migration.py` (also asserted by `test_package_has_no_legacy_imports_or_paths`).

## Checks (final tree)

| Check | Command | Result |
| :-- | :-- | :-- |
| Final source regression | `uv run python -m unittest discover -s tests` | 143 tests OK, exit 0 (`check-unittest.log`) |
| Isolated skill install, copied launcher and installed wheel | `uv run tests/check_distribution.py` | 273 assertions, 0 failed, 0 unverified, exit 0 (`check-distribution.log`) |
| Lint | `uvx ruff check skills/prosevoice tests` | All checks passed (`ruff.log`) |
| Checker negative control | `KINDS` mutated in memory, same script | exit 1, wheel and copy surfaces FAILED (`checker-mutation.log`) |

## Preservation

`.agents/`, `.claude/` and `skills-lock.json` remain untracked and were not read into or modified by any check: the installer ran only in a temp scratch repo with an isolated HOME. Momotron history, the plan and other attempts were not modified. Nothing was committed, published or installed into the real home. No real project was migrated.

## Residual limits

- The installer check uses the local source path, not GitHub, and covers only `-a claude-code -a pi` at project scope. Global-scope installation and the pi/Codex/OpenCode user targets are covered by unit tests, not by a live installer run.
- `harper-cli` presence varies by machine. The checker does not run `lint` against real Harper; unit tests cover lint with stubs and the skipped path.
- uv and npm caches are shared with the developer's caches to avoid repeated downloads; they hold no skill or harness state.

## Correction: Pyright possibly-unbound `payload` (same attempt, second turn)

In `tests/check_distribution.py`, `Helper.__call__`'s `json.JSONDecodeError` branch called `CHECK.ok(False, ...)`, which always raises `Failed`. Pyright could not infer that, so it reported `payload` as possibly unbound at the envelope assertions. I added an explicit `raise AssertionError("unreachable: CHECK.ok(False, ...) raises Failed")` after that call. No diagnostic was suppressed and no placeholder payload was introduced. Behavior is unchanged: a non-JSON output still raises `Failed` with the command's stdout/stderr through `CHECK.ok`, and the new line is unreachable.

| Check after correction | Command | Result |
| :-- | :-- | :-- |
| Type check | `uvx pyright tests/check_distribution.py` | 0 errors, 0 warnings (`pyright.log`) |
| Lint | `uvx ruff check skills/prosevoice tests` | All checks passed (`ruff.log`) |
| Distribution check | `uv run tests/check_distribution.py` | 273 assertions, 0 failed, 0 unverified, exit 0 (`check-distribution.log`) |

The unit suite is unaffected; this change touches only the developer checker. `final-status.txt` and `final-diffstat.txt` were refreshed.
