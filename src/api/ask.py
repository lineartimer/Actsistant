from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field, StringConstraints

from core.agents.search_agent import answer_question


# Keep the question well inside the context window
MAX_QUESTION_LENGTH = 2000


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
        examples=["Is AI that screens job applications considered high-risk?"]
    )


@ask_router.post("/api/ask")
async def ask(request: AskRequest) -> dict:
    answer = await answer_question(request.question)

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
