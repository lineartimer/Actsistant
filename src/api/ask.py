from fastapi import APIRouter


ask_router = APIRouter()

@ask_router.get("/api/ask")
async def ask(query: str) -> dict:
    return {
        "result": "Hello World!",
        "sources": [{
                "title": "A heading",
                "score": "1.0",
                "source": "Some content"
            }
        ]
    }