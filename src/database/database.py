import asyncio
from dataclasses import asdict, dataclass, fields
import structlog
import time
import weaviate
from weaviate.classes.config import Configure, DataType, Property, Tokenization
from weaviate.classes.query import MetadataQuery
from weaviate.collections import Collection
from weaviate.exceptions import WeaviateConnectionError, WeaviateStartUpError
from weaviate.util import generate_uuid5

from config import EMBEDDING_MODEL, WEAVIATE_GRPC_PORT, WEAVIATE_HOST, WEAVIATE_PORT
from database.chunker import Chunk, chunk
from database.download import download_act
from database.embedding import embed_documents, embed_query


COLLECTION_NAME = "EuAiActChunk"
VECTOR_NAME = "embedding"

CONNECTION_TIMEOUT = 60

# Hybrid search: 0 is keyword only (BM25), 1 is vector only
HYBRID_ALPHA = 0.8


_logger = structlog.get_logger(__name__)

_client: weaviate.WeaviateClient | None = None


@dataclass
class Hit:
    chunk: Chunk
    score: float


class DatabaseError(Exception):
    pass


def connect_database() -> weaviate.WeaviateClient:
    deadline = time.monotonic() + CONNECTION_TIMEOUT

    while True:
        try:
            return weaviate.connect_to_local(
                host=WEAVIATE_HOST,
                port=WEAVIATE_PORT,
                grpc_port=WEAVIATE_GRPC_PORT
            )

        except (WeaviateStartUpError, WeaviateConnectionError):
            if time.monotonic() >= deadline:
                raise

            time.sleep(2)


async def initialize_database() -> None:
    global _client

    _client = connect_database()

    try:
        collection = _create_collection(_client)

        if _is_populated(collection):
            return

        xhtml = await download_act()
        chunks = chunk(xhtml)
        vectors = await embed_documents([_document(c) for c in chunks])

        _insert_chunks(collection, chunks, vectors)

        _logger.info("EU AI Act stored in database", chunks=len(chunks))

    except Exception:
        close_database()
        raise


def close_database() -> None:
    global _client

    if _client is not None:
        _client.close()
        _client = None


async def search_chunks(query: str, limit: int = 5) -> list[Hit]:
    if _client is None:
        raise DatabaseError("Database is not initialized")

    collection = _client.collections.get(COLLECTION_NAME)
    vector = await embed_query(query)

    # The Weaviate client is synchronous and its query would block the event loop,
    # stalling every other request, so it runs in a worker thread
    response = await asyncio.to_thread(
        collection.query.hybrid,
        query=query,
        vector=vector,
        target_vector=VECTOR_NAME,
        alpha=HYBRID_ALPHA,
        limit=limit,
        return_metadata=MetadataQuery(score=True)
    )

    return [
        Hit(chunk=_to_chunk(obj.properties), score=obj.metadata.score)
        for obj in response.objects
    ]


def _create_collection(client: weaviate.WeaviateClient) -> Collection:
    description = _description()

    if client.collections.exists(COLLECTION_NAME):
        collection = client.collections.get(COLLECTION_NAME)

        if collection.config.get().description == description:
            return collection
        
        _logger.info("Embedding model changed, rebuilding database", model=EMBEDDING_MODEL)

        client.collections.delete(COLLECTION_NAME)

    # Weaviate runs without a vectorizer module (see docker-compose.yml),
    # so vectors are computed by the app and supplied when objects are inserted
    return client.collections.create(
        COLLECTION_NAME,
        description=description,
        vector_config=Configure.Vectors.self_provided(name=VECTOR_NAME),
        properties=[
            Property(name="chunk_id", data_type=DataType.TEXT, tokenization=Tokenization.FIELD),
            Property(name="kind", data_type=DataType.TEXT, tokenization=Tokenization.FIELD),
            Property(name="heading", data_type=DataType.TEXT),
            Property(name="title", data_type=DataType.TEXT),
            Property(name="chapter", data_type=DataType.TEXT),
            Property(name="section", data_type=DataType.TEXT),
            Property(name="article", data_type=DataType.INT),
            Property(name="paragraph", data_type=DataType.TEXT, tokenization=Tokenization.FIELD),
            Property(name="text", data_type=DataType.TEXT),
            Property(name="position", data_type=DataType.INT)
        ]
    )


def _description() -> str:
    # The embedding model is recorded in the description of the collection,
    # so that a change of model is detected on startup
    return f"EU AI Act chunked by paragraph embedded with {EMBEDDING_MODEL}."


def _is_populated(collection: Collection) -> bool:
    return collection.aggregate.over_all(total_count=True).total_count > 0


def _document(chunk: Chunk) -> str:
    # The embedded text of a chunk starts with its heading and title
    heading = f"{chunk.heading} – {chunk.title}" if chunk.title else chunk.heading

    return f"{heading}\n{chunk.text}"


def _insert_chunks(
    collection: Collection,
    chunks: list[Chunk],
    vectors: list[list[float]]
) -> None:
    with collection.batch.fixed_size(batch_size=100) as batch:
        for chunk, vector in zip(chunks, vectors, strict=True):
            properties = {
                key: value for key, value in asdict(chunk).items() if value is not None
            }

            batch.add_object(
                properties=properties,
                vector={VECTOR_NAME: vector},
                uuid=generate_uuid5(chunk.chunk_id)
            )

    failed = collection.batch.failed_objects
    if failed:
        raise DatabaseError(
            f"{len(failed)} of {len(chunks)} chunks could not be stored: {failed[0].message}"
        )


def _to_chunk(properties: dict) -> Chunk:
    return Chunk(**{field.name: properties.get(field.name) for field in fields(Chunk)})
