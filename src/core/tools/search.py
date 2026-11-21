from langchain_core.tools import tool
import structlog

from database.database import Hit, search_chunks


_logger = structlog.get_logger(__name__)


# The passages are returned twice: as text for the language model (content) and as
# Hit objects for the application (artifact), so that the sources can be reported
@tool(parse_docstring=True, response_format="content_and_artifact")
async def search_eu_ai_act(query: str) -> tuple[str, list[Hit]]:
    """
    Searches the text of the EU AI Act (Regulation (EU) 2024/1689) and returns the
    passages most relevant to the query: recitals, article paragraphs and annexes, each
    with its citation heading such as "Article 6(1)".

    Args:
        query: What to look for in the Act, as a question or a short description.
    """

    hits = await search_chunks(query)

    _logger.info("Searched the EU AI Act", query=query, hits=len(hits))

    return _format(hits), hits


def _format(hits: list[Hit]) -> str:
    if not hits:
        return "No passage of the EU AI Act matched the query."

    return "\n\n".join(_passage(number, hit) for number, hit in enumerate(hits, start=1))


def _passage(number: int, hit: Hit) -> str:
    chunk = hit.chunk
    heading = f"{chunk.heading} – {chunk.title}" if chunk.title else chunk.heading

    return f"[{number}] {heading}\n{chunk.text}"
