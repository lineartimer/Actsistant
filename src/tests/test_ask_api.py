from fastapi.testclient import TestClient
import pytest

import api.ask as ask_api
from api.ask import MAX_QUESTION_LENGTH
from core.agents.search_agent import Answer
from database.chunker import Chunk
from database.database import Hit
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
