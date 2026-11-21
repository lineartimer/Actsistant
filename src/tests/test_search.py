import asyncio
import json
from pathlib import Path

from database.database import (
    COLLECTION_NAME,
    Hit,
    close_database,
    connect_database,
    initialize_database,
    search_chunks
)


DATASET_PATH = Path(__file__).with_name("golden_dataset.json")

# Ratio of seaches returning the correct chunk
MIN_SEARCH_HIT_RATE = 0.8


def test_search():
    questions = json.loads(DATASET_PATH.read_text(encoding="utf-8"))["questions"]

    with connect_database() as client:
        assert client.collections.exists(COLLECTION_NAME), (
            f"Collection {COLLECTION_NAME} does not exist, start the app once to create it"
        )

    results = asyncio.run(_search_all(questions))

    answerable = [(question, hits) for question, hits in results if question["answerable"]]
    hit_count = sum(_rank(question, hits) is not None for question, hits in answerable)
    hit_rate = hit_count / len(answerable)

    print(f"\nSearch hit rate: {hit_count}/{len(answerable)} = {hit_rate:.0%}")

    assert hit_rate >= MIN_SEARCH_HIT_RATE, (
        f"Only {hit_rate:.0%} of the questions returned an expected chunk, "
        f"at least {MIN_SEARCH_HIT_RATE:.0%} is required."
    )


async def _search_all(questions: list[dict]) -> list[tuple[dict, list[Hit]]]:
    await initialize_database()

    try:
        return [(question, await search_chunks(question["question"])) for question in questions]

    finally:
        close_database()


def _rank(question: dict, hits: list[Hit]) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        if hit.chunk.chunk_id in question["expected_chunk_ids"]:
            return rank

    return None
