from dataclasses import dataclass
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
import structlog

from config import CHAT_MODEL, OLLAMA_URL
from core.tools.search import search_eu_ai_act
from database.database import Hit


SYSTEM_PROMPT = (
    "You are Actsistant, an assistant that answers questions about the EU AI Act "
    "(Regulation (EU) 2024/1689).\n\n"
    "Always call search_eu_ai_act first to retrieve the passages of the Act relevant to "
    "the question, then answer based only on those passages. Cite the passages you rely "
    "on by their heading, for example \"Article 6(1)\" or \"Recital 12\". If the passages "
    "do not answer the question, say so instead of guessing."
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


@dataclass
class Answer:
    text: str
    hits: list[Hit]


def build_agent() -> CompiledStateGraph:
    """
    Builds the agent: a tool calling loop in which the model searches the EU AI Act
    and answers from the passages it found.

        START -> agent -> (tool calls?) -> tools -> agent -> ... -> END
    """

    model = ChatOllama(
        model=CHAT_MODEL,
        base_url=OLLAMA_URL,
        temperature=0,
        num_ctx=CTX_SIZE,
        # Qwen3 is a thinking model and thinking is allowed by default.
        # Switch on if you want to trade speed for quality
        reasoning=False
    ).bind_tools(TOOLS)

    async def call_model(state: MessagesState) -> dict:
        response = await model.ainvoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])

        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    # Errors such as an unreachable database are raised instead of being fed back
    # to the model as text, which it would answer with an apology
    graph.add_node("tools", ToolNode(TOOLS, handle_tool_errors=False))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


agent = build_agent()


async def answer_question(question: str) -> Answer:
    """
    Answers a question about the EU AI Act, returning the answer of the model and
    the passages of the Act it retrieved.
    """

    state = await agent.ainvoke(
        {"messages": [HumanMessage(question)]},
        config={"recursion_limit": RECURSION_LIMIT}
    )
    messages = state["messages"]
    hits = _retrieved_hits(messages)

    _logger.info("Question answered", question=question, passages=len(hits))

    return Answer(text=messages[-1].text, hits=hits)


def _retrieved_hits(messages: list[AnyMessage]) -> list[Hit]:
    # The model may search more than once, so the same chunk can turn up twice
    hits: dict[str, Hit] = {}

    for message in messages:
        if isinstance(message, ToolMessage) and message.artifact:
            for hit in message.artifact:
                hits.setdefault(hit.chunk.chunk_id, hit)

    return list(hits.values())
