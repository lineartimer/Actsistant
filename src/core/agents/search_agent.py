from dataclasses import dataclass
from langchain_core.messages import HumanMessage, SystemMessage, ToolCall, ToolMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field, create_model
import structlog
from typing import Literal, TypedDict

from config import CLOUD_CHAT_MODEL, LOCAL_CHAT_MODEL, LOCAL_RUN_ONLY, OLLAMA_URL, OPENAI_API_KEY
from core.tools.search import search_eu_ai_act
from database.database import Hit


SYSTEM_PROMPT = (
    "You are Actsistant, an assistant that answers questions about the EU AI Act "
    "(Regulation (EU) 2024/1689).\n\n"
    "The question comes with the passages of the Act retrieved for it. Answer based only "
    "on those passages. Cite every passage you rely on inline by its bracketed heading "
    "exactly as shown, for example [Article 6(1)] or [Recital 12]. If the passages do not "
    "answer the question, say so instead of guessing."
)

# Context window of the chat model in tokens. Ollama's default is too small to hold
# the system prompt, the question and the retrieved passages, and Ollama silently
# drops the beginning of the conversation when it does not fit
CTX_SIZE = 16384


_logger = structlog.get_logger(__name__)


class StructuredAnswer(BaseModel):
    """
    The final answer to the question about the EU AI Act.
    """

    text: str = Field(
        description="The answer for the user, based only on the retrieved passages and "
                    "citing them inline by heading, for example [Article 6(1)]"
    )
    sources: list[str] = Field(
        description="The headings of the retrieved passages the answer relies on, "
                    "empty if none of them answers the question"
    )


class AgentState(TypedDict):
    question: str
    # The retrieved passages twice: as text for the model and as objects for the application
    passages: str
    hits: list[Hit]
    answer: StructuredAnswer


@dataclass
class Answer:
    text: str
    hits: list[Hit]


def answer_schema(headings: list[str]) -> type[StructuredAnswer]:
    """
    The schema of the answer to one question: the sources are restricted to the
    headings of the passages retrieved for it, so that the model cannot cite a
    passage it has not seen. Without retrieved passages nothing can be cited.
    """

    if not headings:
        return StructuredAnswer

    heading = Literal[tuple(headings)]  # type: ignore[valid-type]

    return create_model(
        "StructuredAnswer",
        __base__=StructuredAnswer,
        sources=(
            list[heading],
            Field(description=StructuredAnswer.model_fields["sources"].description)
        )
    )


def build_agent() -> CompiledStateGraph:
    """
    Builds the agent: a fixed two-step pipeline in which the search tool is called once
    with the question and the model then answers from the passages it returned, in its
    structured form.

        START -> search -> answer -> END
    """

    if OPENAI_API_KEY and not LOCAL_RUN_ONLY:
        model = ChatOpenAI(
            model=CLOUD_CHAT_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
            # GPT-6 is a reasoning model and reasons by default. The temperature needs
            # reasoning switched off. Switch on if you want to trade speed for quality
            reasoning_effort="none"
        )
    else:
        model = ChatOllama(
            model=LOCAL_CHAT_MODEL,
            base_url=OLLAMA_URL,
            temperature=0,
            num_ctx=CTX_SIZE,
            # Qwen3 is a thinking model and thinking is allowed by default.
            # Switch on if you want to trade speed for quality
            reasoning=False
        )

    async def search(state: AgentState) -> dict:
        # Invoked as a tool call, the tool returns the passages both as text and as Hit
        # objects. Errors such as an unreachable database are raised, not answered
        result: ToolMessage = await search_eu_ai_act.ainvoke(
            ToolCall(
                name=search_eu_ai_act.name,
                args={"query": state["question"]},
                id="search",
                type="tool_call"
            )
        )

        return {"passages": result.content, "hits": result.artifact}

    async def answer(state: AgentState) -> dict:
        headings = [hit.chunk.heading for hit in state["hits"]]
        structured_model = model.with_structured_output(answer_schema(headings))

        answer = await structured_model.ainvoke([
            SystemMessage(SYSTEM_PROMPT),
            HumanMessage(
                f"Passages of the EU AI Act retrieved for the question:\n\n"
                f"{state['passages']}\n\n"
                f"Question: {state['question']}"
            )
        ])

        return {"answer": answer}

    graph = StateGraph(AgentState)
    graph.add_node("search", search)
    graph.add_node("answer", answer)
    graph.add_edge(START, "search")
    graph.add_edge("search", "answer")
    graph.add_edge("answer", END)

    return graph.compile()


agent = build_agent()


async def answer_question(question: str) -> Answer:
    """
    Answers a question about the EU AI Act, returning the answer of the model and
    those of the retrieved passages of the Act that it names as its sources.
    """

    state = await agent.ainvoke({"question": question})
    answer: StructuredAnswer = state["answer"]
    retrieved: list[Hit] = state["hits"]
    hits = [hit for hit in retrieved if hit.chunk.heading in answer.sources]

    # Only possible when nothing was retrieved or the provider does not enforce the schema
    unknown = set(answer.sources) - {hit.chunk.heading for hit in retrieved}
    if unknown:
        _logger.warning("Answer names sources that were not retrieved", sources=sorted(unknown))

    _logger.info(
        "Question answered",
        question=question,
        cited=[hit.chunk.heading for hit in hits]
    )

    return Answer(text=answer.text, hits=hits)
