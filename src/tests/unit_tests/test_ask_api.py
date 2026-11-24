import asyncio
from fastapi.testclient import TestClient
import pytest
from structlog.testing import capture_logs

import api.ask as ask_api
from api.ask import MAX_QUESTION_LENGTH
import core.agents.answering as answering
from core.agents.answering import Answer, StructuredAnswer
import core.tools.search as search_tool
from database.chunker import Chunk
from database.database import Hit
from database.embedding import EmbeddingError
from main import app


QUESTION = "Which AI systems does the Act classify as high-risk?"

HIT = Hit(
    chunk=Chunk(
        chunk_id="art_6.par_1",
        kind="article",
        heading="Article 6(1)",
        title="Classification rules for high-risk AI systems",
        chapter="III",
        section="1",
        article=6,
        paragraph="1",
        text="Irrespective of whether an AI system is placed on the market or put into "
             "service independently of the products referred to in points (a) and (b), "
             "that AI system shall be considered to be high-risk where both of the "
             "following conditions are fulfilled: ..."
    ),
    score=0.9
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    questions: list[str] = []

    async def answer_question(question: str) -> Answer:
        questions.append(question)
        return Answer(text=f"Stubbed answer [{HIT.chunk.heading}]", hits=[HIT])

    monkeypatch.setattr(ask_api, "answer_question", answer_question)
    return questions


class FakeChatModel:
    def __init__(self):
        self.reply = None
        self.schema = None
        self.messages = None

    def with_structured_output(self, schema: type[StructuredAnswer]) -> "FakeChatModel":
        self.schema = schema
        return self

    async def ainvoke(self, messages: list) -> StructuredAnswer:
        assert self.reply is not None, "The test must set model.reply"

        self.messages = messages
        return await self.reply(self.schema)


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeChatModel:
    model = FakeChatModel()

    monkeypatch.setattr(answering, "ChatOpenAI", lambda **_: model)
    monkeypatch.setattr(answering, "ChatOllama", lambda **_: model)
    monkeypatch.setattr(answering, "agent", answering.build_agent())

    return model


def returning(hits: list[Hit]):
    async def search_chunks(query: str) -> list[Hit]:
        return hits

    return search_chunks


def test_question_in_body_is_answered(client: TestClient, asked: list[str]):
    response = client.post("/api/ask", json={"question": f"  {QUESTION}  "})

    assert response.status_code == 200
    assert response.json() == {
        "result": f"Stubbed answer [{HIT.chunk.heading}]",
        "sources": [{"heading": HIT.chunk.heading, "text": HIT.chunk.text}]
    }
    assert asked == [QUESTION], "The question should reach the agent without surrounding whitespace"


def test_longest_question_is_accepted(client: TestClient, asked: list[str]):
    response = client.post("/api/ask", json={"question": "x" * MAX_QUESTION_LENGTH})

    assert response.status_code == 200
    assert len(asked) == 1


def test_failed_answer_is_a_500_without_details(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def answer_question(question: str) -> Answer:
        raise ConnectionError("Ollama is not reachable at http://localhost:11434")

    monkeypatch.setattr(ask_api, "answer_question", answer_question)

    with capture_logs() as logs:
        response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 500
    assert "localhost" not in response.text, "The cause must not leak to the caller"

    [error] = [log for log in logs if log["log_level"] == "error"]
    assert error["event"] == "Answering the question failed"
    assert error["question"] == QUESTION
    assert error["exc_info"], "The cause belongs in the log"


def test_timed_out_answer_is_a_504(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def answer_question(question: str) -> Answer:
        await asyncio.sleep(10)
        return Answer(text="Too late", hits=[])

    monkeypatch.setattr(ask_api, "answer_question", answer_question)
    monkeypatch.setattr(ask_api, "ANSWER_TIMEOUT", 0.05)

    with capture_logs() as logs:
        response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 504

    [error] = [log for log in logs if log["log_level"] == "error"]
    assert error["event"] == "Answering the question timed out"
    assert error["timeout"] == 0.05


def test_empty_search_is_answered_without_sources(
    client: TestClient, model: FakeChatModel, monkeypatch: pytest.MonkeyPatch
):
    async def reply(schema: type[StructuredAnswer]) -> StructuredAnswer:
        return schema(text="The passages do not answer the question.", sources=[])

    monkeypatch.setattr(search_tool, "search_chunks", returning([]))
    model.reply = reply

    response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json() == {"result": "The passages do not answer the question.", "sources": []}
    assert "No passage of the EU AI Act matched the query." in model.messages[-1].content, (
        "The model must be told that nothing was retrieved"
    )


def test_source_made_up_for_an_empty_search_is_dropped(
    client: TestClient, model: FakeChatModel, monkeypatch: pytest.MonkeyPatch
):
    async def reply(schema: type[StructuredAnswer]) -> StructuredAnswer:
        # Without retrieved passages the schema cannot restrict the sources
        return schema(text="Fines are set out in [Article 99].", sources=["Article 99"])

    monkeypatch.setattr(search_tool, "search_chunks", returning([]))
    model.reply = reply

    with capture_logs() as logs:
        response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json()["sources"] == []

    [warning] = [log for log in logs if log["log_level"] == "warning"]
    assert warning["event"] == "Answer names sources that were not retrieved"
    assert warning["sources"] == ["Article 99"]


def test_failed_embedding_is_a_500_without_details(
    client: TestClient, model: FakeChatModel, monkeypatch: pytest.MonkeyPatch
):
    async def search_chunks(query: str) -> list[Hit]:
        raise EmbeddingError(
            "Ollama is not reachable at http://localhost:11434: Connection refused"
        )

    monkeypatch.setattr(search_tool, "search_chunks", search_chunks)

    with capture_logs() as logs:
        response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 500
    assert "localhost" not in response.text, "The cause must not leak to the caller"
    assert model.messages is None, "The model must not be called when the search fails"

    [error] = [log for log in logs if log["log_level"] == "error"]
    assert error["event"] == "Answering the question failed"


def test_hanging_embedding_is_a_504(
    client: TestClient, model: FakeChatModel, monkeypatch: pytest.MonkeyPatch
):
    async def search_chunks(query: str) -> list[Hit]:
        await asyncio.sleep(10)
        return []

    monkeypatch.setattr(search_tool, "search_chunks", search_chunks)
    monkeypatch.setattr(ask_api, "ANSWER_TIMEOUT", 0.05)

    response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 504
    assert model.messages is None, "The model must not be called when the search hangs"


def test_failed_model_is_a_500_without_details(
    client: TestClient, model: FakeChatModel, monkeypatch: pytest.MonkeyPatch
):
    async def reply(schema: type[StructuredAnswer]) -> StructuredAnswer:
        raise ConnectionError("OpenAI is not reachable at https://api.openai.com")

    monkeypatch.setattr(search_tool, "search_chunks", returning([HIT]))
    model.reply = reply

    with capture_logs() as logs:
        response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 500
    assert "openai.com" not in response.text, "The cause must not leak to the caller"

    [error] = [log for log in logs if log["log_level"] == "error"]
    assert error["event"] == "Answering the question failed"


def test_hanging_model_is_a_504(
    client: TestClient, model: FakeChatModel, monkeypatch: pytest.MonkeyPatch
):
    async def reply(schema: type[StructuredAnswer]) -> StructuredAnswer:
        await asyncio.sleep(10)
        return schema(text="Too late", sources=[])

    monkeypatch.setattr(search_tool, "search_chunks", returning([HIT]))
    model.reply = reply
    monkeypatch.setattr(ask_api, "ANSWER_TIMEOUT", 0.05)

    response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 504


def test_question_in_query_string_is_not_allowed(client: TestClient, asked: list[str]):
    response = client.get("/api/ask", params={"question": QUESTION})

    assert response.status_code == 405
    assert asked == []


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({}, id="missing"),
        pytest.param({"question": ""}, id="empty"),
        pytest.param({"question": "   \n\t"}, id="blank"),
        pytest.param({"question": "x" * (MAX_QUESTION_LENGTH + 1)}, id="too long"),
        pytest.param({"question": None}, id="null"),
        pytest.param({"question": 42}, id="not a string"),
        pytest.param({"query": QUESTION}, id="wrong field name")
    ]
)
def test_invalid_question_is_rejected(client: TestClient, asked: list[str], body: dict):
    response = client.post("/api/ask", json=body)

    assert response.status_code == 422
    assert asked == [], "A rejected request must not reach the agent"


def test_malformed_json_is_rejected(client: TestClient, asked: list[str]):
    response = client.post(
        "/api/ask",
        content=f'{{"question": "{QUESTION}"',
        headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert asked == []
