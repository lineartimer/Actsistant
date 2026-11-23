from dataclasses import dataclass
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field, create_model
import structlog
from typing import Literal

from config import CLOUD_CHAT_MODEL, LOCAL_CHAT_MODEL, LOCAL_RUN_ONLY, OLLAMA_URL, OPENAI_API_KEY
from core.tools.search import search_eu_ai_act
from database.database import Hit


SYSTEM_PROMPT = (
    "You are Actsistant, an assistant that answers questions about the EU AI Act "
    "(Regulation (EU) 2024/1689).\n\n"
    "Always call search_eu_ai_act first to retrieve the passages of the Act relevant to "
    "the question, then answer based only on those passages. Cite every passage you rely "
    "on inline by its bracketed heading exactly as shown in the search results, for "
    "example [Article 6(1)] or [Recital 12]. If the passages do not answer the question, "
    "say so instead of guessing."
)

TOOLS = [search_eu_ai_act]

# Context window of the chat model in tokens. Ollama's default is too small to hold
# the system prompt, the question and the retrieved passages, and Ollama silently
# drops the beginning of the conversation when it does not fit
CTX_SIZE = 16384

# Maximum number of graph steps per question, so that a model that keeps calling
# the search tool is stopped
RECURSION_LIMIT = 10


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


class AgentState(MessagesState):
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
    Builds the agent: a tool calling loop in which the model searches the EU AI Act
    and answers from the passages it found, followed by a step that turns the
    conversation into a structured answer.

        START -> agent -> (tool calls?) -> tools -> agent -> ... -> respond -> END
    """

    if OPENAI_API_KEY and not LOCAL_RUN_ONLY:
        model = ChatOpenAI(
            model=CLOUD_CHAT_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
            # GPT-6 is a reasoning model and reasons by default. Tool calling and the
            # temperature need reasoning switched off. Switch on if you want to trade
            # speed for quality
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
    agent_model = model.bind_tools(TOOLS)

    async def call_model(state: AgentState) -> dict:
        response = await agent_model.ainvoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])

        return {"messages": [response]}

    async def respond(state: AgentState) -> dict:
        # Not every provider can combine tool calling with structured output in one
        # model call, so the answer is put into its structured form in a call of its own
        headings = [hit.chunk.heading for hit in _retrieved_hits(state["messages"])]
        structured_model = model.with_structured_output(answer_schema(headings))

        answer = await structured_model.ainvoke(
            [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
        )

        return {"answer": answer}

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    # Errors such as an unreachable database are raised instead of being fed back
    # to the model as text, which it would answer with an apology
    graph.add_node("tools", ToolNode(TOOLS, handle_tool_errors=False))
    graph.add_node("respond", respond)
    graph.add_edge(START, "agent")
    # Once the model stops calling tools, its answer is put into the structured form
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "respond"})
    graph.add_edge("tools", "agent")
    graph.add_edge("respond", END)

    return graph.compile()


agent = build_agent()


async def answer_question(question: str) -> Answer:
    """
    Answers a question about the EU AI Act, returning the answer of the model and
    those of the retrieved passages of the Act that it names as its sources.
    """

    state = await agent.ainvoke(
        {"messages": [HumanMessage(question)]},
        config={"recursion_limit": RECURSION_LIMIT}
    )
    answer: StructuredAnswer = state["answer"]
    retrieved = _retrieved_hits(state["messages"])
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


def _retrieved_hits(messages: list[AnyMessage]) -> list[Hit]:
    # The model may search more than once, so the same chunk can turn up twice
    hits: dict[str, Hit] = {}

    for message in messages:
        if isinstance(message, ToolMessage) and message.artifact:
            for hit in message.artifact:
                hits.setdefault(hit.chunk.chunk_id, hit)

    return list(hits.values())
