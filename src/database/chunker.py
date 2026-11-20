from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET


# A unit of the Act (recital, article paragraph, annex) longer than this
# that consists of a list of points is split into one chunk per point
MAX_CHUNK_LENGTH = 2500

_INDENT = "  "

# CSS classes of the headings and titles of chapters, sections, articles and annexes
_HEADING_CLASSES = {
    "oj-ti-art",
    "oj-sti-art",
    "oj-ti-section-1",
    "oj-ti-section-2",
    "oj-doc-ti",
    "eli-title"
}

# Sub-headings within annexes, e.g. "Section A — ..." or "3. Quality management system"
_SUBHEADING_CLASS = "oj-ti-grseq-1"

# Footnote markers in the text, e.g. the "(1)" in "...Social Committee (1),"
_FOOTNOTE_CLASS = "oj-note-tag"


@dataclass
class Chunk:
    chunk_id: str       # Stable id, e.g. "rct_12", "art_6.par_1", "art_5.par_1.pt_a", "anx_VIII.sec_A.pt_1"
    kind: str           # "recital", "article" or "annex"
    heading: str        # Citation, e.g. "Article 6(1)", "Article 5(1), point (a)", "Annex VIII, Section A, point 1"
    title: str          # Title of the article or annex ("" for recitals)
    chapter: str        # e.g. "Chapter III – HIGH-RISK AI SYSTEMS" ("" outside the enacting terms)
    section: str        # e.g. "Section 1 – Classification of AI systems as high-risk" or an annex sub-heading
    article: int | None
    paragraph: str      # Number of the paragraph within the article ("" if the article has none)
    text: str
    position: int = 0   # Order within the Act


@dataclass
class _Piece:
    text: str
    section: str = ""   # Annex sub-heading the piece belongs to ("" if none)
    label: str = ""     # Label of the point, e.g. "(a)", "3.1." or "—" ("" for a whole unit)
    ordinal: int = 0    # Number of the point within its section, starting at 1


def chunk_act(xhtml: bytes) -> list[Chunk]:
    """
    Splits the EU AI Act into chunks along its structure: one chunk per recital,
    per numbered paragraph of an article (or per article if it has no numbered
    paragraphs) and per annex. Long units that consist of a list of points are
    split further into one chunk per point.

    The Publications Office XHTML uses ELI markup: every recital, chapter, section,
    article and annex is a div with a stable id ("rct_12", "cpt_III", "cpt_III.sct_1",
    "art_6", "anx_III"), the numbered paragraphs of an article are divs with ids like
    "006.001" and enumerated points are two-column tables (label, text).

    Args:
        xhtml: The Act as published by the Publications Office.
    """

    root = ET.fromstring(xhtml)
    elements = {
        element.get("id"): element for element in root.iter() if element.get("id")
    }

    chunks = []

    # Preamble: recitals (the citations before them are skipped)
    for child in elements["pbl_1"]:
        if re.fullmatch(r"rct_\d+", child.get("id", "")):
            chunks.append(_chunk_recital(child))

    # Enacting terms: chapters, sections and articles
    for chapter in elements["enc_1"]:
        chunks.extend(_chunk_chapter(chapter))

    # Annexes
    annex_ids = sorted(
        (element_id for element_id in elements if re.fullmatch(r"anx_[IVXL]+", element_id)),
        key=_roman_value
    )

    for annex_id in annex_ids:
        chunks.extend(_chunk_annex(elements[annex_id]))

    for position, chunk in enumerate(chunks):
        chunk.position = position

    return chunks


def _chunk_recital(element: ET.Element) -> Chunk:
    number = element.get("id").split("_")[1]

    return Chunk(
        chunk_id=f"rct_{number}",
        kind="recital",
        heading=f"Recital {number}",
        title="",
        chapter="",
        section="",
        article=None,
        paragraph="",
        text="\n".join(_render(element))
    )


def _chunk_chapter(
    element: ET.Element, chapter: str = "", section: str = ""
) -> list[Chunk]:
    """
    Walks a chapter (or a section of a chapter) down to its articles.
    """

    element_id = element.get("id", "")

    if re.fullmatch(r"cpt_[IVXL]+", element_id):
        # "CHAPTER III" -> "III"
        number = _heading(element, "oj-ti-section-1").split()[-1]
        chapter = f"Chapter {number} – {_title(element)}"

    elif ".sct_" in element_id:
        # "SECTION 1" -> "1"
        number = _heading(element, "oj-ti-section-1").split()[-1]
        section = f"Section {number} – {_title(element)}"

    chunks = []
    for child in element:
        child_id = child.get("id", "")

        if re.fullmatch(r"art_\d+", child_id):
            chunks.extend(_chunk_article(child, chapter, section))

        elif child_id.startswith("cpt_") and ".tit_" not in child_id:
            # A section of the chapter
            chunks.extend(_chunk_chapter(child, chapter, section))

    return chunks


def _chunk_article(element: ET.Element, chapter: str, section: str) -> list[Chunk]:
    number = int(element.get("id").split("_")[1])
    fields = {
        "kind": "article",
        "title": _title(element),
        "chapter": chapter,
        "section": section,
        "article": number
    }

    body = _body(element)
    paragraphs = [
        child for child in body if re.fullmatch(r"\d{3}\.\d{3}", child.get("id", ""))
    ]
    unnumbered = [child for child in body if child not in paragraphs]

    chunks = []

    if unnumbered:
        # An article without numbered paragraphs (e.g. Article 3, Definitions)
        chunks.extend(_chunk_unit(
            f"art_{number}", f"Article {number}", unnumbered, paragraph="", **fields
        ))

    for paragraph in paragraphs:
        # "006.001" -> "1"
        paragraph_number = str(int(paragraph.get("id").split(".")[1]))

        chunks.extend(_chunk_unit(
            f"art_{number}.par_{paragraph_number}",
            f"Article {number}({paragraph_number})",
            list(paragraph),
            paragraph=paragraph_number,
            **fields
        ))

    return chunks


def _chunk_annex(element: ET.Element) -> list[Chunk]:
    numeral = element.get("id").split("_")[1]

    # The document titles of an annex are e.g. "ANNEX III" and the title proper
    titles = [_text(child) for child in element if "oj-doc-ti" in _css_class(child)]

    return _chunk_unit(
        f"anx_{numeral}",
        f"Annex {numeral}",
        _body(element),
        kind="annex",
        title=" ".join(titles[1:]),
        chapter="",
        section="",
        article=None,
        paragraph=""
    )


def _chunk_unit(
    base_id: str, citation: str, children: list[ET.Element], **fields
) -> list[Chunk]:
    """
    Turns a unit of the Act (article paragraph, article, annex) into chunks.

    Args:
        base_id: Chunk id of the unit, e.g. "art_6.par_1".
        citation: How the unit is cited, e.g. "Article 6(1)".
        children: Elements that make up the body of the unit.
        fields: Fields of the chunks that are the same for the whole unit.
    """

    chunks = []
    for piece in _split_into_pieces(children):
        parts = _citation_parts(piece)

        chunk = Chunk(
            chunk_id=".".join([base_id] + [_slug(part) for part in parts]),
            heading=", ".join([citation] + parts),
            text=piece.text,
            **fields
        )

        if piece.section:
            chunk.section = piece.section

        chunks.append(chunk)

    return chunks


def _split_into_pieces(children: list[ET.Element]) -> list[_Piece]:
    """
    Returns a single piece for a short unit. A long unit that consists of a list
    of points is split into one piece per point, each prefixed with the lead-in
    text (and annex sub-heading) that precedes the points.
    """

    text = "\n".join(_render(children))
    has_points = any(_tag(child) == "table" for child in children)

    if len(text) <= MAX_CHUNK_LENGTH or not has_points:
        return [_Piece(text=text)]

    pieces = []
    for heading, members in _split_into_sections(children):
        lead_in = [heading] if heading else []

        if not any(_tag(member) == "table" for member in members):
            # A sub-heading without points (e.g. an introduction) is one piece
            pieces.append(_Piece(
                text="\n".join(lead_in + _render(members)), section=heading
            ))

            continue

        point_lines = None
        label = ""
        ordinal = 0

        for member in members:
            if _tag(member) == "table":
                if point_lines is not None:
                    pieces.append(_Piece("\n".join(point_lines), heading, label, ordinal))

                label = _point_label(member)
                ordinal += 1
                point_lines = lead_in + _render_table(member, 0)

            elif point_lines is None:
                # Text before the first point
                lead_in.extend(_render([member]))

            else:
                # Text after a point belongs to that point
                point_lines.extend(_render([member]))

        pieces.append(_Piece("\n".join(point_lines), heading, label, ordinal))

    return pieces


def _split_into_sections(
    children: list[ET.Element]
) -> list[tuple[str, list[ET.Element]]]:
    """
    Groups the children of a unit by annex sub-heading.
    """

    sections = []
    heading, members = "", []

    for child in children:
        if _SUBHEADING_CLASS not in _css_class(child):
            members.append(child)

        elif members:
            sections.append((heading, members))
            heading, members = _text(child), []

        else:
            # Consecutive sub-headings, e.g. "Section 1" followed by its title
            heading = f"{heading} – {_text(child)}" if heading else _text(child)

    sections.append((heading, members))

    return [section for section in sections if section[1]]


def _citation_parts(piece: _Piece) -> list[str]:
    """
    Where the piece is within its unit, e.g. ["Section A", "point 1"] or ["point 1(a)"].
    """

    parts = []

    if piece.section:
        # "Section A — ..." -> "Section A", "3. Quality management system" -> "point 3"
        match = re.match(r"(Section\s+)?([A-Z]|\d+)(?:[.\s]|$)", piece.section)

        if match is None:
            parts.append(piece.section)

        elif match[1]:
            parts.append(f"Section {match[2]}")

        else:
            parts.append(f"point {match[2]}")

    if piece.label:
        # "(a)" -> "a", "3.1." -> "3.1", "—" -> ""
        label = re.sub(r"[^\w.]", "", piece.label).rstrip(".")

        if not label:
            # The points of a dash list have no label of their own
            parts.append(f"item {piece.ordinal}")

        elif parts and parts[-1].startswith("point") and piece.label.startswith("("):
            # A lettered point under a numbered sub-heading: "point 1(a)"
            parts[-1] += piece.label

        elif parts and parts[-1].startswith("point") and label.startswith(parts[-1][6:] + "."):
            # A sub-numbered point: "point 3.1" rather than "point 3, point 3.1"
            parts[-1] = f"point {label}"

        elif piece.label.startswith("("):
            parts.append(f"point {piece.label}")

        else:
            parts.append(f"point {label}")

    return parts


def _slug(part: str) -> str:
    """
    "Section A" -> "sec_A", "point 1(a)" -> "pt_1_a", "point 3.1" -> "pt_3_1"
    """

    part = part.replace("Section", "sec").replace("point", "pt")

    return re.sub(r"\W+", "_", part).strip("_")


def _render(elements, depth: int = 0) -> list[str]:
    """
    Renders block content (paragraphs, point tables, nested divs) as indented lines.
    """

    lines = []
    for element in elements:
        tag = _tag(element)

        if tag == "table":
            lines.extend(_render_table(element, depth))

        elif tag in ("div", "tbody", "tr", "td"):
            lines.extend(_render(element, depth))

        elif tag not in ("col", "hr", "img", "br"):
            # Paragraphs and inline elements
            text = _text(element)
            if text:
                lines.append(_INDENT * depth + text)

    return lines


def _render_table(table: ET.Element, depth: int) -> list[str]:
    """
    Renders enumerated points as "(a) text", with nested points indented one level.
    """

    lines = []
    for row in _rows(table):
        cells = []
        for cell in row:
            if _tag(cell) == "td":
                rendered = _render(cell)
                if rendered:
                    cells.append(rendered)

        if not cells:
            continue

        if len(cells) == 1:
            lines.extend(_INDENT * depth + line for line in cells[0])
            continue

        # The first cell is the label of the point, the rest is its text
        label = " ".join(cells[0])
        body = [line for cell in cells[1:] for line in cell]

        lines.append(_INDENT * depth + f"{label} {body[0]}")
        lines.extend(_INDENT * (depth + 1) + line for line in body[1:])

    return lines


def _rows(table: ET.Element):
    for child in table:
        if _tag(child) == "tr":
            yield child

        elif _tag(child) == "tbody":
            for row in child:
                if _tag(row) == "tr":
                    yield row


def _point_label(table: ET.Element) -> str:
    """
    Label of the first point in a table, e.g. "(a)", "1.", "3.1." or "—".
    """

    for row in _rows(table):
        for cell in row:
            if _tag(cell) == "td":
                text = _text(cell)
                if text:
                    return text.split()[0]

    return ""


def _body(element: ET.Element) -> list[ET.Element]:
    """
    Children of a unit without its headings and title.
    """

    return [
        child for child in element
        if not _HEADING_CLASSES & set(_css_class(child).split())
    ]


def _title(element: ET.Element) -> str:
    """
    Title of a chapter, section or article (the text of its "eli-title" child).
    """

    for child in element:
        if "eli-title" in _css_class(child):
            return _text(child)

    return ""


def _heading(element: ET.Element, css_class: str) -> str:
    """
    Text of the first descendant with the given CSS class, e.g. "CHAPTER III".
    """

    for descendant in element.iter():
        if css_class in _css_class(descendant):
            return _text(descendant)

    return ""


def _text(element: ET.Element) -> str:
    """
    Text of an element without footnote markers and with whitespace collapsed.
    """

    parts = []

    def collect(e: ET.Element) -> None:
        if _FOOTNOTE_CLASS in _css_class(e):
            return

        if e.text:
            parts.append(e.text)

        for child in e:
            collect(child)

            if child.tail:
                parts.append(child.tail)

    collect(element)

    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _tag(element: ET.Element) -> str:
    # Strip the XHTML namespace
    return element.tag.rsplit("}", 1)[-1]


def _css_class(element: ET.Element) -> str:
    return element.get("class", "")


def _roman_value(annex_id: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50}
    digits = [values[c] for c in annex_id.split("_")[1]]

    return sum(
        -digit if i + 1 < len(digits) and digit < digits[i + 1] else digit
        for i, digit in enumerate(digits)
    )
