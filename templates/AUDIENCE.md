# Audience

Who the prose is for, and how to keep it readable for that reader. The `prose-voice` skill reads
this file from the git root (or `~/.config/prose-voice/AUDIENCE.md` for prose drafted outside a
repo). It is **required**: absent or empty, the skill is a silent no-op. How the author writes
lives in [`VOICE.md`](VOICE.md).

A copy of this file in a document's **own directory** wholly replaces this one for the documents
there. Use one when a folder targets a different reader — a customer deck, a post series for a
different audience, mail to a specific team. A single document can override the reader persona
alone with a frontmatter `audience:` line.

<!-- Keep the section headings below. prose-voice agents look up "The reader" and the
de-jargon table by name. Delete the HTML comments when done. -->

## The reader

<!-- The target persona: role, what they already know, what they do not, why they are reading,
and what they should be able to do or decide afterwards. -->

_Persona._

## Register

<!-- The publication register to write in (for example a named magazine or newspaper), and
what that implies for tone and assumed background. -->

_Register._

## Loosen for the reader (density)

<!-- How much to unpack for this reader: when to define a term, when to add an example, how
much argument per paragraph they can absorb. -->

- _Rule_.

## De-jargon table

The voice-stylist auto-applies a row **only** when the match is exact and the replacement is
grammatical in the sentence. Everything else is surfaced.

| Insider term | Plain replacement |
| :----------- | :---------------- |
| _term_       | _replacement_     |

## Figure text (accessibility vs. print)

<!-- How image alt text and titles are written for this reader. See RENDER.md if present. -->

_Convention._
