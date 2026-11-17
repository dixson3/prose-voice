"""Essay mechanics: supplemental prose extraction, premise fingerprints and READY checks.

Ported without behavioral change from the former ``extract_prose.py``,
``premise_fingerprint.py`` and ``ready_preconditions.py`` helpers. READY resolves the
``illustrations`` sidecar through the shared configuration layer rather than a sibling
skill import.

Extraction recovers Harper-skipped reader-facing prose (single-line frontmatter prose
values, image alt/title text, fenced-code comment lines and plain fences) into one
snippet per line with a back-map to (path, line, 0-based char column, region, coarse).
Offsets are in character (codepoint) space.

The premise fingerprint is SHA-256 over the normalized ``title`` plus the ``thesis:``
field, or the mechanically selected first body paragraph when no thesis is declared;
the reported fingerprint is the first 16 hex characters.

READY: only ``<!-- illus:ID -->`` anchors opt into visual checks; every active anchor
needs a ``## illus:ID`` block in the resolved illustrations artifact with a chosen
asset id or ``selected: no-image``. Stale blocks without anchors are ignored. No
``[needs-source]`` token may remain in any part's body.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .config import Config, artifact_paths, config_for_essay

# ======================================================================= extraction

# Frontmatter keys whose values are reader-facing prose worth linting.
FRONTMATTER_PROSE_KEYS = {"title", "subtitle", "description", "summary", "dek"}

# Comment markers recognized inside fenced code blocks.
COMMENT_MARKERS = ("#", "//", "--", ";")


class Snippet:
    """One extracted prose snippet and its back-map to the source."""

    __slots__ = ("coarse", "orig_col_offset", "orig_line", "region", "text")

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
                if value.startswith((">", "|")):
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
        title_col = 0  # meaningful only when title_text is set
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
        if not in_fence and stripped.startswith(("```", "~~~")):
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

# ======================================================================= premise

def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter-fields, body). Only the flat scalar fields we need are parsed.

    Handles `key: value`, `key: "value"`, and YAML block scalars (`key: >-` / `key: |`) whose
    continuation lines are more-indented. Good enough for `title:` and `thesis:`; not a full YAML
    parser (no external dep).
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    # find the closing fence
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1 :])

    fields: dict[str, str] = {}
    i = 0
    key_re = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
    while i < len(fm_lines):
        line = fm_lines[i]
        m = key_re.match(line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in (">", ">-", "|", "|-", ">+", "|+"):
            # block scalar: gather more-indented continuation lines
            block: list[str] = []
            i += 1
            while i < len(fm_lines) and (fm_lines[i].strip() == "" or fm_lines[i][:1] in (" ", "\t")):
                block.append(fm_lines[i].strip())
                i += 1
            fields[key] = " ".join(b for b in block if b)
            continue
        # strip matching surrounding quotes
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        fields[key] = val
        i += 1
    return fields, body


def first_body_paragraph(body: str) -> str:
    """Mechanical fallback: the first paragraph of real prose after the frontmatter.

    Skips blank lines, ATX headings (`#`), images (`![`), and HTML comments (`<!--`). A paragraph
    is the first maximal run of non-blank lines once a qualifying line is found.
    """
    lines = body.splitlines()
    para: list[str] = []
    started = False
    for line in lines:
        s = line.strip()
        if not started:
            if s == "" or s.startswith(("#", "![", "<!--")):
                continue
            started = True
            para.append(s)
        else:
            if s == "":
                break
            para.append(s)
    return " ".join(para)


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)  # punctuation -> space
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fingerprint(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    fields, body = split_frontmatter(text)
    title = fields.get("title", "")
    thesis = fields.get("thesis", "")
    if thesis:
        region = "thesis-field"
        source = f"{title}\n{thesis}"
    else:
        region = "first-body-paragraph"
        source = f"{title}\n{first_body_paragraph(body)}"
    norm = normalize(source)
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    return {
        "fingerprint": digest,
        "region": region,
        "title": title,
        "normalized_len": str(len(norm)),
    }


# ======================================================================= READY

ANCHOR_RE = re.compile(r"<!--\s*illus:([A-Za-z0-9]+)\s*-->")
BLOCK_HDR_RE = re.compile(r"^##\s+illus:([A-Za-z0-9]+)\b")
SELECTED_RE = re.compile(r"^selected:\s*(\S+)", re.IGNORECASE)
NEEDS_SOURCE_RE = re.compile(r"\[needs-source\]")


def _strip_frontmatter(lines):
    """Return (body_lines, start_index) with YAML frontmatter removed."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1 :], i + 1
    return lines, 0


def sidecar_path(config: Config, essay: Path) -> Path:
    return artifact_paths(config, essay)["illustrations"]


def parse_sidecar(text: str):
    """Return {anchor_id: selected_asset_or_None}."""
    blocks = {}
    current = None
    for line in text.splitlines():
        heading = BLOCK_HDR_RE.match(line)
        if heading:
            current = heading.group(1)
            blocks[current] = None
            continue
        selected = SELECTED_RE.match(line.strip())
        if current is not None and selected:
            blocks[current] = selected.group(1)
    return blocks


def active_anchors(essay_text: str) -> list[str]:
    body, _ = _strip_frontmatter(essay_text.splitlines())
    return sorted(set(ANCHOR_RE.findall("\n".join(body))))


def check_image(config: Config, essay: Path):
    side = sidecar_path(config, essay)
    sidecar_text = side.read_text(encoding="utf-8") if side.is_file() else None
    return image_outcome(essay.read_text(encoding="utf-8"), sidecar_text, side)


def image_outcome(essay_text: str, sidecar_text: str | None, side: Path) -> dict:
    """Active-anchor visual outcome from essay text and its sidecar text (``None`` = absent)."""
    anchors = active_anchors(essay_text)
    blocks = parse_sidecar(sidecar_text) if sidecar_text is not None else {}
    blockers = []
    for anchor in anchors:
        if anchor not in blocks:
            blockers.append(f"illus:{anchor}: no sidecar block")
        elif blocks[anchor] is None or blocks[anchor].lower() == "unresolved":
            blockers.append(f"illus:{anchor}: selection unresolved")
    return {
        "resolved": not blockers,
        "sidecar": str(side),
        "sidecar_present": sidecar_text is not None,
        "planned_visual_count": len(anchors),
        "blockers": blockers,
    }


def check_source(essays):
    hits = []
    for essay in essays:
        lines = essay.read_text(encoding="utf-8").splitlines()
        body, offset = _strip_frontmatter(lines)
        for i, line in enumerate(body):
            if NEEDS_SOURCE_RE.search(line):
                hits.append({"file": str(essay), "line": offset + i + 1, "text": line.strip()})
    return {"resolved": not hits, "needs_source_count": len(hits), "locations": hits}


READY_LIMITATIONS = (
    ("Mechanical check only: it finds unresolved [needs-source] markers; it does not verify sources, "
     "facts or citations. A web-enabled source review is required by the skill, not proven here."),
    "Explicit source overrides are reported by the caller, never applied by this check.",
    ("Visual checks cover only active <!-- illus:ID --> anchors; unanchored sections carry no visual "
     "obligation and stale sidecar blocks without anchors are ignored."),
    "A clear result does not establish that the essay is correct or ready to publish.",
)


def check_ready(config: Config, essays: list[Path]) -> dict:
    """READY preconditions over ordered essay parts: visuals per part, sources across all."""
    image = {str(essay): check_image(config_for_essay(config, essay), essay) for essay in essays}
    source = check_source(essays)
    ready = all(v["resolved"] for v in image.values()) and source["resolved"]
    return {"ready": ready, "image": image, "source": source, "limitations": list(READY_LIMITATIONS)}
