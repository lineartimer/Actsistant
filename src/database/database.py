from dataclasses import asdict
import structlog
import time
import weaviate
from weaviate.classes.config import Configure, DataType, Property, Tokenization
from weaviate.collections import Collection
from weaviate.exceptions import WeaviateConnectionError, WeaviateStartUpError
from weaviate.util import generate_uuid5

from config import WEAVIATE_GRPC_PORT, WEAVIATE_HOST, WEAVIATE_PORT
from database.chunker import Chunk, chunk
from database.download import download_act


COLLECTION_NAME = "EuAiActChunk"

CONNECTION_TIMEOUT = 60


_logger = structlog.get_logger(__name__)


class DatabaseError(Exception):
    pass


def connect_database() -> weaviate.WeaviateClient:
    """
    Connects to Weaviate database.
    """

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
    """
    Creates the collection of chunks of the EU AI Act and, on the first startup,
    downloads the Act, chunks it and stores it in the database.
    """

    with connect_database() as client:
        collection = _create_collection(client)

        if _is_populated(collection):
            return

        xhtml = await download_act()
        chunks = chunk(xhtml)

        _insert_chunks(collection, chunks)

        _logger.info("EU AI Act stored in database", chunks=len(chunks))


def _create_collection(client: weaviate.WeaviateClient) -> Collection:
    if client.collections.exists(COLLECTION_NAME):
        return client.collections.get(COLLECTION_NAME)

    # Weaviate runs without a vectorizer module (see docker-compose.yml),
    # so vectors have to be supplied by the app when objects are inserted
    return client.collections.create(
        COLLECTION_NAME,
        description=(
            "EU AI Act (Regulation (EU) 2024/1689) chunked by recital, "
            "article paragraph and annex"
        ),
        vector_config=Configure.Vectors.self_provided(),
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


def _is_populated(collection: Collection) -> bool:
    return collection.aggregate.over_all(total_count=True).total_count > 0


def _insert_chunks(collection: Collection, chunks: list[Chunk]) -> None:
    with collection.batch.fixed_size(batch_size=100) as batch:
        for chunk in chunks:
            properties = {
                key: value for key, value in asdict(chunk).items() if value is not None
            }
            
            batch.add_object(properties=properties, uuid=generate_uuid5(chunk.chunk_id))

    failed = collection.batch.failed_objects
    if failed:
        raise DatabaseError(
            f"{len(failed)} of {len(chunks)} chunks could not be stored: {failed[0].message}"
        )
