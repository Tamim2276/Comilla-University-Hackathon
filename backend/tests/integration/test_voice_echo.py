"""Voice webhooks in echo mode (D1-A3: FR-CALL-01, 03, 04; SRS 3.1). No network."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain import messages_bn
from app.interfaces.voice.router import citizen_number
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    no_store = Path(__file__).parent / "no_store"  # never created
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        chroma_dir=no_store,
        tfidf_model_path=no_store / "r.joblib",
        agent_engine="stub",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def turn(client: TestClient, speech: str = "", call_sid: str = "CA1") -> str:
    form = {"CallSid": call_sid, "SpeechResult": speech, "From": "+8801712345678", "Direction": "inbound"}
    response = client.post("/voice/respond", data=form)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    return response.text


@pytest.mark.parametrize("path", ["/voice/incoming", "/voice/start"])
def test_call_start_greets_and_listens(client: TestClient, path: str) -> None:
    response = client.post(path, data={"CallSid": "CA1"})
    assert response.status_code == 200
    assert messages_bn.GREETING in response.text
    assert '<Gather action="/voice/respond"' in response.text
    assert 'language="bn-BD"' in response.text


def test_respond_echoes_the_speech_then_continue(client: TestClient) -> None:
    xml = turn(client, "বয়স্ক ভাতা")
    assert "বয়স্ক ভাতা" in xml
    assert messages_bn.CONTINUE in xml
    assert xml.index("<Gather") < xml.index("বয়স্ক ভাতা")  # spoken inside the Gather (barge-in)


def test_first_silence_reprompts_second_says_goodbye(client: TestClient) -> None:
    first = turn(client)
    assert messages_bn.REPROMPT in first
    assert "<Gather" in first

    second = turn(client, "   ")
    assert messages_bn.GOODBYE in second
    assert "<Hangup />" in second
    assert "<Gather" not in second


def test_speech_between_silences_resets_the_count(client: TestClient) -> None:
    turn(client)
    turn(client, "হ্যালো")
    assert messages_bn.REPROMPT in turn(client)


def test_silences_are_counted_per_call(client: TestClient) -> None:
    turn(client, call_sid="CA1")
    assert messages_bn.REPROMPT in turn(client, call_sid="CA2")


def test_status_returns_204_and_ends_the_call_state(client: TestClient) -> None:
    turn(client)
    response = client.post("/voice/status", data={"CallSid": "CA1", "CallStatus": "completed"})
    assert response.status_code == 204
    assert messages_bn.REPROMPT in turn(client)  # a fresh count


def test_citizen_number_by_direction() -> None:
    assert citizen_number("+8801711111111", "+15005550006", "inbound") == "+8801711111111"
    assert citizen_number("+15005550006", "+8801711111111", "outbound-api") == "+8801711111111"
