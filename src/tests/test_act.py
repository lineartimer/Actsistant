from pathlib import Path

from database.database import COLLECTION_NAME, connect_database


OUTPUT_PATH = Path(__file__).with_name("test_act.md")

# Structure of Regulation (EU) 2024/1689
RECITALS = 180
ARTICLES = 113
ANNEXES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII"]


def test_act_and_dump_to_md():
    with connect_database() as client:
        assert client.collections.exists(COLLECTION_NAME), (
            f"Collection {COLLECTION_NAME} does not exist, start the app once to create it"
        )

        collection = client.collections.get(COLLECTION_NAME)
        objects = list(collection.iterator(include_vector=True))

    assert objects, f"Collection {COLLECTION_NAME} is empty"

    dimensions = {len(obj.vector.get("default", [])) for obj in objects}
    assert dimensions and 0 not in dimensions, "Some chunks have no vector"
    assert len(dimensions) == 1, f"Vectors have different dimensions: {dimensions}"

    chunks = sorted(
        (obj.properties for obj in objects),
        key=lambda properties: properties["position"]
    )

    OUTPUT_PATH.write_text(_to_markdown(chunks), encoding="utf-8")

    positions = [chunk["position"] for chunk in chunks]
    assert positions == list(range(len(chunks))), "Positions are not contiguous"

    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    assert len(set(chunk_ids)) == len(chunk_ids), "Chunk ids are not unique"

    recitals = {chunk["chunk_id"] for chunk in chunks if chunk["kind"] == "recital"}
    assert recitals == {f"rct_{n}" for n in range(1, RECITALS + 1)}

    articles = {chunk["article"] for chunk in chunks if chunk["kind"] == "article"}
    assert articles == set(range(1, ARTICLES + 1))

    annexes = {chunk["chunk_id"].split(".")[0] for chunk in chunks if chunk["kind"] == "annex"}
    assert annexes == {f"anx_{numeral}" for numeral in ANNEXES}


def _to_markdown(chunks: list[dict]) -> str:
    lines = [
        "EU AI Act - Test",
        "================",
        ""
    ]

    context = {"kind": None, "chapter": None, "section": None, "unit": None}

    for chunk in chunks:
        kind = chunk["kind"]

        if kind != context["kind"]:
            context = {"kind": kind, "chapter": None, "section": None, "unit": None}

            if kind == "recital":
                lines += ["# Preamble", ""]

            elif kind == "annex":
                lines += ["# Annexes", ""]

        if kind == "article":
            if chunk["chapter"] != context["chapter"]:
                context.update(chapter=chunk["chapter"], section=None, unit=None)
                lines += [f"# {chunk['chapter']}", ""]

            if chunk["section"] != context["section"]:
                context.update(section=chunk["section"], unit=None)

                if chunk["section"]:
                    lines += [f"## {chunk['section']}", ""]

            if chunk["article"] != context["unit"]:
                context["unit"] = chunk["article"]
                lines += [f"### Article {chunk['article']} – {chunk['title']}", ""]

        elif kind == "annex":
            annex = chunk["chunk_id"].split(".")[0]

            if annex != context["unit"]:
                context.update(unit=annex, section=None)
                numeral = annex.split("_")[1]
                lines += [f"## Annex {numeral} – {chunk['title']}", ""]

            if chunk["section"] != context["section"]:
                context["section"] = chunk["section"]

                if chunk["section"]:
                    lines += [f"### {chunk['section']}", ""]

        heading_level = "##" if kind == "recital" else "####"
        lines += [
            f"{heading_level} {chunk['heading']} `{chunk['chunk_id']}`",
            "",
            chunk["text"],
            ""
        ]

    return "\n".join(lines)
