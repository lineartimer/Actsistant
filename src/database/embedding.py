import httpx
import structlog

from config import EMBEDDING_MODEL, OLLAMA_URL


# Qwen3 Embedding models expect a question to be prefixed with an instruction that
# describes the retrieval task, while documents are embedded as they are
QUERY_INSTRUCTION = (
    "Given a question about the EU AI Act, retrieve the passages of the Act that answer it"
)

# Number of texts embedded per request
BATCH_SIZE = 32

REQUEST_TIMEOUT = 300


_logger = structlog.get_logger(__name__)


class EmbeddingError(Exception):
    pass


async def embed_documents(texts: list[str]) -> list[list[float]]:
    """
    Embeds documents (chunks of the EU AI Act) with the embedding model served by Ollama.
    """

    vectors = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        for start in range(0, len(texts), BATCH_SIZE):
            vectors.extend(await _embed(client, texts[start:start + BATCH_SIZE]))

            _logger.info("Embedding documents", done=len(vectors), total=len(texts))

    return vectors


async def embed_query(text: str) -> list[float]:
    """
    Embeds a question with the same model as the documents, so that its vector can be
    compared with theirs.
    """

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        [vector] = await _embed(client, [f"Instruct: {QUERY_INSTRUCTION}\nQuery: {text}"])

    return vector


async def _embed(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={
                "model": EMBEDDING_MODEL,
                "input": texts,
                # Fail instead of silently cutting off the end of a text that does not
                # fit into the context window of the model
                "truncate": False
            }
        )

    except httpx.HTTPError as e:
        raise EmbeddingError(f"Ollama is not reachable at {OLLAMA_URL}: {e}") from e

    if response.status_code == 404:
        raise EmbeddingError(
            f"Embedding model {EMBEDDING_MODEL} is not available, "
            f"run: ollama pull {EMBEDDING_MODEL}"
        )

    if response.is_error:
        raise EmbeddingError(f"Embedding failed: {_error_message(response)}")

    return response.json()["embeddings"]


def _error_message(response: httpx.Response) -> str:
    try:
        return response.json()["error"]

    except (ValueError, KeyError, TypeError):
        return f"HTTP {response.status_code}"
