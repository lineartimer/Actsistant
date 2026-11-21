import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StringConstraints
import structlog
from typing import Annotated

from config import ANSWER_TIMEOUT
from core.agents.search_agent import answer_question


# Keep the question well inside the context window
MAX_QUESTION_LENGTH = 2000


_logger = structlog.get_logger(__name__)

ask_router = APIRouter()


class AskRequest(BaseModel):
    """
    A question about the EU AI Act.
    """

    question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH)
    ] = Field(
        description="The question about the EU AI Act",
        examples=["Can my employer use AI to read my emotions at work?"]
    )


@ask_router.post("/api/ask")
async def ask(request: AskRequest) -> dict:
    _logger.info("Ask api called.", question=request.question)

    try:
        async with asyncio.timeout(ANSWER_TIMEOUT):
            answer = await answer_question(request.question)

    except TimeoutError:
        _logger.error(
            "Answering the question timed out",
            question=request.question,
            timeout=ANSWER_TIMEOUT
        )

        raise HTTPException(
            status_code=504,
            detail="Answering the question took too long, please try again later."
        ) from None

    except Exception:
        # The model, the embedding or the database may be the cause, the traceback tells
        _logger.exception("Answering the question failed", question=request.question)
        
        raise HTTPException(
            status_code=500,
            detail="The question could not be answered, please try again later."
        ) from None

    return {
        "result": answer.text,
        "sources": [
            {
                "heading": hit.chunk.heading,
                "text": hit.chunk.text
            }
            for hit in answer.hits
        ]
    }
