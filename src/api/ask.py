from fastapi import APIRouter

from core.agents.search_agent import answer_question


ask_router = APIRouter()

@ask_router.get("/api/ask")
async def ask(query: str) -> dict:
    answer = await answer_question(query)

    return {
        "result": answer.text,
        "sources": [
            {
                "title": hit.chunk.heading,
                "score": hit.score,
                "source": hit.chunk.text
            }
            for hit in answer.hits
        ]
    }
