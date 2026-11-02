# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Extract Harper-skipped reader-facing prose from an essay for a supplemental lint pass.

`harper-cli`, given a `.md` path, is genuinely markdown-aware: it lints body prose,
headings, emphasis, link text, list items — and correctly SKIPS link URLs, inline
code, AND three regions that nonetheless render to a reader:

  * YAML frontmatter prose values (title, subtitle, description, summary, dek);
  * image alt text and title captions  (`![alt](path "title")`); and
  * fenced-code content, including prose comment lines.

This helper recovers exactly those regions into a temp `.md` — ONE snippet per line —
while building a back-map from each temp line to the original (path, line, column,
region) so a finding from a second Harper run on the temp file can be reported at the
right place in the source. It is uv-run, stdlib-only (no new CLI dependency).

All offsets are in CHARACTER (codepoint) space, matching Harper's 1-based char column
(`column`) and char spans (`span.char_start/char_end`). `orig_col_offset` is the 0-BASED
char index in the original line where the snippet's first character sits; the agent maps
a Harper finding at 1-based `column` C within a snippet to original 1-based column
`orig_col_offset + C`.

v1 scope (deliberately conservative — every extracted region is SURFACE-ONLY downstream,
never auto-fixed, so line accuracy matters most and column precision is best-effort):

  * Frontmatter: SINGLE-LINE scalar values only, for an allowlist of prose keys. A folded
    or block scalar (`>` / `|`) collapses >=2 source lines into one snippet and breaks a
    single-`orig_line` map, so it is emitted COARSELY — mapped to the KEY's line with
    `coarse: true` — never char-precise.
  * Images: alt and title are tokenized, not naively `"([^"]*)"`-matched. The title scanner
    handles escaped quotes (`\"`, `\'`) and the `"…"`, `'…'`, and `(…)` title styles;
    multiple images on one line each map separately.
  * Fenced blocks: comment-marker lines (`#`, `//`, `--`, `;`) inside ANY fence have the
    marker stripped (so the snippet is clean prose, not a markdown heading) and the body
    of a PLAIN/unlabeled fence is emitted whole.

Output: writes the temp `.md` to disk (caller cleans up) and prints ONE JSON object to
stdout:

    {"temp_md": "<path>", "count": N,
     "map": {"<temp_line>": {"orig_path","orig_line","orig_col_offset","region","coarse"}}}

`<temp_line>` is the 1-based line number in `temp_md`.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Frontmatter keys whose values are reader-facing prose worth linting.
FRONTMATTER_PROSE_KEYS = {"title", "subtitle", "description", "summary", "dek"}

# Comment markers recognized inside fenced code blocks.
COMMENT_MARKERS = ("#", "//", "--", ";")


class Snippet:
    """One extracted prose snippet and its back-map to the source."""

    __slots__ = ("text", "orig_line", "orig_col_offset", "region", "coarse")

    def __init__(self, text: str, orig_line: int, orig_col_offset: int, region: str, coarse: bool = False):
        self.text = text
        self.orig_line = orig_line  # 1-based
        self.orig_col_offset = orig_col_offset  # 0-based char index in the source line
        self.region = region
        self.coarse = coarse


def strip_yaml_quotes(value: str) -> tuple[str, int]:
    """Strip a single layer of matching YAML quotes.

    Returns (inner_text, leading_offset) where leading_offset is the number of
    characters consumed before the inner text (0 if unquoted, 1 if quoted). This
    keeps column math honest: the inner value starts that many chars into `value`.
    """
    if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
        return value[1:-1], 1
    return value, 0


def extract_frontmatter(lines: list[str]) -> list[Snippet]:
    """Extract prose-key values from a leading YAML frontmatter block, if present."""
    if not lines or lines[0].strip() != "---":
        return []
    # Find the closing fence.
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return []

    snippets: list[Snippet] = []
    i = 1
    while i < end:
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        # Only consider top-level keys (no indent); nested mappings are out of v1 scope.
        if indent == 0 and ":" in stripped:
            key, _, rest = stripped.partition(":")
            key = key.strip()
            if key in FRONTMATTER_PROSE_KEYS:
                value = rest.strip()
                if value.startswith(">") or value.startswith("|"):
                    # Block/folded scalar: collapse following more-indented lines into
                    # one coarse snippet mapped to the KEY's line (never char-precise).
                    block: list[str] = []
                    j = i + 1
                    while j < end:
                        bstr = lines[j].lstrip()
                        bindent = len(lines[j]) - len(bstr)
                        if lines[j].strip() == "" or bindent > indent:
                            if bstr:
                                block.append(bstr)
                            j += 1
                        else:
                            break
                    if block:
                        snippets.append(
                            Snippet(" ".join(block), i + 1, 0, f"frontmatter:{key}", coarse=True)
                        )
                    i = j
                    continue
                if value:
                    inner, lead = strip_yaml_quotes(value)
                    if inner.strip():
                        # Char offset of the value within the source line: position of
                        # `value` in the line, plus the quote lead.
                        col = line.index(value) + lead
                        snippets.append(Snippet(inner, i + 1, col, f"frontmatter:{key}"))
        i += 1
    return snippets


def scan_images(line: str, lineno: int) -> list[Snippet]:
    """Tokenize every `![alt](url "title")` on a line into alt and title snippets.

    Hand-rolled scanner (not a naive regex) so it survives escaped quotes inside a
    title and the three title-quoting styles. Multiple images on one line each map
    to their own source column.
    """
    out: list[Snippet] = []
    n = len(line)
    k = 0
    while k < n:
        # Find the next image start `![`.
        idx = line.find("![", k)
        if idx == -1:
            break
        # Read alt up to the matching `]` (no nested brackets assumed).
        alt_start = idx + 2
        close = line.find("]", alt_start)
        if close == -1:
            break
        alt = line[alt_start:close]
        # Must be immediately followed by `(`.
        if close + 1 >= n or line[close + 1] != "(":
            k = close + 1
            continue
        # Scan the parenthetical: url [whitespace title].
        p = close + 2
        # url = run of non-space, non-`)` chars.
        while p < n and line[p] not in (" ", "\t", ")"):
            p += 1
        title_text = None
        title_col = None
        # Optional whitespace then a title.
        q = p
        while q < n and line[q] in (" ", "\t"):
            q += 1
        if q < n and line[q] in ('"', "'", "("):
            open_ch = line[q]
            close_ch = ")" if open_ch == "(" else open_ch
            t = q + 1
            buf_start = t
            while t < n:
                if line[t] == "\\" and t + 1 < n:
                    t += 2  # escaped char (e.g. \" or \') — do not terminate
                    continue
                if line[t] == close_ch:
                    break
                t += 1
            if t <= n:
                title_text = line[buf_start:t]
                title_col = buf_start
            # advance p past the closing paren of the parenthetical
            close_paren = line.find(")", t)
            p = close_paren + 1 if close_paren != -1 else n
        else:
            close_paren = line.find(")", p)
            p = close_paren + 1 if close_paren != -1 else n

        if alt.strip():
            out.append(Snippet(alt, lineno, alt_start, "image-alt"))
        if title_text is not None and title_text.strip():
            out.append(Snippet(title_text, lineno, title_col, "image-title"))
        k = p
    return out


def match_comment(line: str) -> tuple[int, str] | None:
    """If `line` is a comment-marker line, return (text_col_offset, text)."""
    stripped = line.lstrip()
    indent = len(line) - len(stripped)
    for marker in COMMENT_MARKERS:
        if stripped.startswith(marker):
            after = stripped[len(marker):]
            # consume a single optional space so the snippet is clean prose
            extra = 1 if after.startswith(" ") else 0
            text = after[extra:]
            return indent + len(marker) + extra, text
    return None


def extract_body(lines: list[str], body_start: int) -> list[Snippet]:
    """Walk body lines, tracking fenced blocks; extract images, fence comments, fence prose."""
    snippets: list[Snippet] = []
    in_fence = False
    fence_marker = ""
    fence_is_plain = False

    for i in range(body_start, len(lines)):
        line = lines[i]
        stripped = line.strip()

        # Fence open/close detection.
        if not in_fence and (stripped.startswith("```") or stripped.startswith("~~~")):
            marker = "```" if stripped.startswith("```") else "~~~"
            info = stripped[len(marker):].strip()
            in_fence = True
            fence_marker = marker
            fence_is_plain = info == ""
            continue
        if in_fence:
            if stripped.startswith(fence_marker) and stripped[len(fence_marker):].strip() == "":
                in_fence = False
                continue
            # Inside a fence: comment lines (any fence) -> stripped prose;
            # plain-fence body lines -> whole line.
            cm = match_comment(line)
            if cm is not None:
                col, text = cm
                if text.strip():
                    snippets.append(Snippet(text, i + 1, col, "fenced-comment"))
            elif fence_is_plain and stripped:
                col = len(line) - len(line.lstrip())
                snippets.append(Snippet(line.strip(), i + 1, col, "fenced-prose"))
            continue

        # Outside a fence: extract image alt/title.
        snippets.extend(scan_images(line, i + 1))

    return snippets


def find_body_start(lines: list[str]) -> int:
    """Return the 0-based index of the first body line after any frontmatter block."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                return i + 1
    return 0


def extract(path: Path) -> list[Snippet]:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    snippets = extract_frontmatter(lines)
    snippets += extract_body(lines, find_body_start(lines))
    return snippets


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Extract Harper-skipped reader-facing prose.")
    p.add_argument("essay", help="path to the essay .md")
    p.add_argument("--out-md", default=None, help="temp .md output path (default: temp file)")
    args = p.parse_args(argv)

    essay = Path(args.essay)
    if not essay.is_file():
        print(f"error: essay not found: {essay}", file=sys.stderr)
        return 2

    snippets = extract(essay)

    if args.out_md:
        out_md = Path(args.out_md)
    else:
        fd = tempfile.NamedTemporaryFile(mode="w", suffix=".prose.md", delete=False, encoding="utf-8")
        fd.close()
        out_md = Path(fd.name)

    # One snippet per line; temp line number is 1-based.
    out_md.write_text("\n".join(s.text for s in snippets) + ("\n" if snippets else ""), encoding="utf-8")

    mapping = {
        str(idx + 1): {
            "orig_path": str(essay),
            "orig_line": s.orig_line,
            "orig_col_offset": s.orig_col_offset,
            "region": s.region,
            "coarse": s.coarse,
        }
        for idx, s in enumerate(snippets)
    }
    print(json.dumps({"temp_md": str(out_md), "count": len(snippets), "map": mapping}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
