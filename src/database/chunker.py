from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET


MAX_CHUNK_LENGTH = 2500

_INDENT = "  "

# Headings (css classes)
_HEADING_CLASSES = {
    "oj-ti-art",
    "oj-sti-art",
    "oj-ti-section-1",
    "oj-ti-section-2",
    "oj-doc-ti",
    "eli-title"
}

# Sub-headings (css classes)
_SUBHEADING_CLASS = "oj-ti-grseq-1"

# Footnotes (css classes)
_FOOTNOTE_CLASS = "oj-note-tag"


@dataclass
class Chunk:
    chunk_id: str
    kind: str
    heading: str
    title: str
    chapter: str
    section: str
    article: int | None
    paragraph: str
    text: str
    position: int = 0


@dataclass
class _Piece:
    text: str
    section: str = ""
    label: str = ""
    ordinal: int = 0


def chunk(xhtml: bytes) -> list[Chunk]:
    """
    Splits the EU AI Act into chunks along its structure.

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

    # Preamble
    for child in elements["pbl_1"]:
        if re.fullmatch(r"rct_\d+", child.get("id", "")):
            chunks.append(_chunk_recital(child))

    # Chapters, sections and articles
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
    element: ET.Element,
    chapter: str = "",
    section: str = ""
) -> list[Chunk]:
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
        # An article without numbered paragraphs
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
    base_id: str,
    citation: str,
    children: list[ET.Element],
    **fields
) -> list[Chunk]:
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
                lead_in.extend(_render([member]))

            else:
                point_lines.extend(_render([member]))

        pieces.append(_Piece("\n".join(point_lines), heading, label, ordinal))

    return pieces


def _split_into_sections(
    children: list[ET.Element]
) -> list[tuple[str, list[ET.Element]]]:
    sections = []
    heading, members = "", []

    for child in children:
        if _SUBHEADING_CLASS not in _css_class(child):
            members.append(child)

        elif members:
            sections.append((heading, members))
            heading, members = _text(child), []

        else:
            heading = f"{heading} – {_text(child)}" if heading else _text(child)

    sections.append((heading, members))

    return [section for section in sections if section[1]]


def _citation_parts(piece: _Piece) -> list[str]:
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
            parts.append(f"item {piece.ordinal}")

        elif parts and parts[-1].startswith("point") and piece.label.startswith("("):
            parts[-1] += piece.label

        elif parts and parts[-1].startswith("point") and label.startswith(parts[-1][6:] + "."):
            parts[-1] = f"point {label}"

        elif piece.label.startswith("("):
            parts.append(f"point {piece.label}")

        else:
            parts.append(f"point {label}")

    return parts


def _slug(part: str) -> str:
    part = part.replace("Section", "sec").replace("point", "pt")
    return re.sub(r"\W+", "_", part).strip("_")


def _render(elements, depth: int = 0) -> list[str]:
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
    for row in _rows(table):
        for cell in row:
            if _tag(cell) == "td":
                text = _text(cell)
                if text:
                    return text.split()[0]

    return ""


def _body(element: ET.Element) -> list[ET.Element]:
    return [
        child for child in element
        if not _HEADING_CLASSES & set(_css_class(child).split())
    ]


def _title(element: ET.Element) -> str:
    for child in element:
        if "eli-title" in _css_class(child):
            return _text(child)

    return ""


def _heading(element: ET.Element, css_class: str) -> str:
    for descendant in element.iter():
        if css_class in _css_class(descendant):
            return _text(descendant)

    return ""


def _text(element: ET.Element) -> str:
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
