# Voice

How the author writes. Applied to every prose deliverable — blog posts, documents, slide decks
and emails — by the `prose-voice` skill, which reads this file from the git root (or
`~/.config/prose-voice/VOICE.md` for prose drafted outside a repo). It is **required**: absent or
empty, the skill is a silent no-op. Who the prose is for lives in [`AUDIENCE.md`](AUDIENCE.md).

<!-- Keep the section headings below. prose-voice agents look up "How the author argues",
"Register", "Readability", "Do / Don't", "Generative-cadence tells" and "Forms" by name.
Replace each placeholder with your own rules; delete the HTML comments when done. -->

## How the author argues (patterns to preserve)

<!-- The moves that make the prose recognisably yours. Anything listed here is PROTECTED:
reviewers surface changes that touch it and never auto-apply them. Typical entries: how verdicts
are stated, preferred analogy sources, how hedges are owned, how pieces open and close. -->

- _Pattern_ — what it looks like, and a short example.

## Register / mechanics

<!-- Person and tense, sentence length, contractions, punctuation habits (dashes, serial comma),
heading case, numbers, lists vs prose, and spelling dialect (us / uk / au / ca / in — passed to
Harper). The copy-editor enforces these. -->

- _Rule_.

## Readability (flow & density)

<!-- Mechanical limits the readability-critic enforces: maximum sentence and paragraph length,
acronyms per paragraph, nesting of clauses, how often to give the reader a concrete example. -->

- _Limit_ — the threshold and what to do when a passage crosses it.

## Do / Don't

<!-- The DRAFT gate checks this list on every surfaced draft. Include the anti-meta-narration
rule: the prose does not announce what it is about to do or what it just did. -->

| Do                        | Don't                                                 |
| :------------------------ | :---------------------------------------------------- |
| State the claim directly. | Announce the claim ("In this section I will argue…"). |
| _Your rule_               | _Its opposite_                                        |

## Generative-cadence tells (AI slop)

<!-- Patterns that read as machine-generated and should be flagged: rule-of-three lists,
"It's not X, it's Y" pivots, stacked em-dash asides, summary closers, and so on. -->

- _Tell_ — how to recognise it, and the fix.

## Forms

<!-- Optional per-form rules. The skill resolves a form (post / document / slides / email) for
every piece and applies the matching subsection; a missing subsection falls back to the defaults
in agents/voice-stylist.md and agents/readability-critic.md. Delete the forms you never write. -->

### post

- _Rule_ (length, opening move, how a post closes, footnote style).

### document

- _Rule_ (conclusion-first, heading style, summary length, when to use a table).

### slides

- _Rule_ (word budget per slide, title-as-claim, what goes in speaker notes, bullet punctuation).

### email

- _Rule_ (subject-line pattern, greeting and sign-off, length for a request vs. an update, one
  ask per mail).
