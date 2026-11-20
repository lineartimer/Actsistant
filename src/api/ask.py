from fastapi import APIRouter

from database.database import search_chunks


ask_router = APIRouter()

@ask_router.get("/api/ask")
async def ask(query: str) -> dict:
    hits = await search_chunks(query)

    return {
        "result": "Hello World!",
        "sources": [
            {
                "title": hit.chunk.heading,
                "score": hit.score,
                "source": hit.chunk.text
            }
            for hit in hits
        ]
    }
