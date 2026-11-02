# Illustration style

The house visual style for essay illustrations. The `blog-voice` illustrator drops the
**Style block** below verbatim into every `naba` prompt. Optional: absent, the illustrator reports
the style undefined and skips.

## Resolution order

The illustrator reads the **first** file that exists:

1. `Incubator/<slug>/ILLUSTRATIONS.md` — per-incubator override.
2. Git-root `ILLUSTRATIONS.md` — the repo default.

## Schema

- **Style block** — the `## Style block` section. A self-contained visual brief: medium,
  palette, background, register, hard exclusions. Keep it prompt-ready, with no commentary about
  the repo inside it.
- **Aspect hints (optional)** — a `## Aspect` section naming hero and section aspect ratios.
  Absent, the illustrator uses a wide hero and the `naba` default for sections.

A per-incubator file needs only its own `## Style block` (and optionally `## Aspect`).

## Style block

_Medium and technique._

_Palette._

_Background._

_Hard exclusions._

## Aspect

- Hero: `16:9`
- Section: `1:1`
