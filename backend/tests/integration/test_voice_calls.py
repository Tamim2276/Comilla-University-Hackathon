"""Voice webhooks end to end with the stub engine (D1-A3, D1-A5: FR-CALL-01 to 06, 09, 11). No network."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings
from app.domain import messages_bn
from app.domain.errors import LLMUnavailable
from app.interfaces.voice.router import citizen_number
from app.main import create_app

PHONE = "+8801712345678"
STUB_SPEECH = "পুরুষদের ৬৫ বছর হলে আবেদন করা যায়"  # start of the stub engine's answer


@pytest.fixture
def client() -> Iterator[TestClient]:
    no_store = Path(__file__).parent / "no_store"  # never created
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        chroma_dir=no_store,
        tfidf_model_path=no_store / "r.joblib",
        agent_engine="stub",
        sms_backend="console",
        public_url="https://example.ngrok-free.dev",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def turn(client: TestClient, speech: str = "", call_sid: str = "CA1") -> str:
    form = {"CallSid": call_sid, "SpeechResult": speech, "From": PHONE, "Direction": "inbound"}
    response = client.post("/voice/respond", data=form)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    return response.text


def call_row(client: TestClient, call_sid: str = "CA1") -> dict | None:
    factory = client.app.state.container.session_factory
    with factory() as session:
        sql = text("SELECT phone, direction, turns, ended_at FROM calls WHERE call_sid = :sid")
        row = session.execute(sql, {"sid": call_sid}).mappings().first()
    return dict(row) if row else None


# ---------------------------------------------------------------- start and greeting


@pytest.mark.parametrize(
    ("path", "form", "direction"),
    [
        ("/voice/incoming", {"From": PHONE, "To": "+15005550006", "Direction": "inbound"}, "inbound"),
        ("/voice/start", {"From": "+15005550006", "To": PHONE, "Direction": "outbound-api"}, "outbound-api"),
    ],
)
def test_call_start_greets_and_stores_the_call(
    client: TestClient, path: str, form: dict, direction: str
) -> None:
    response = client.post(path, data={"CallSid": "CA1", **form})
    assert response.status_code == 200
    assert messages_bn.GREETING in response.text
    assert '<Gather action="https://example.ngrok-free.dev/voice/respond"' in response.text
    assert 'language="bn-BD"' in response.text
    assert call_row(client) == {"phone": PHONE, "direction": direction, "turns": 0, "ended_at": None}


def test_foreign_caller_still_hears_the_greeting(client: TestClient) -> None:
    response = client.post("/voice/incoming", data={"CallSid": "CA1", "From": "+15005550006"})
    assert messages_bn.GREETING in response.text
    assert call_row(client) is None


# ---------------------------------------------------------------- turns


def test_question_gets_the_agent_answer_then_continue(client: TestClient) -> None:
    xml = turn(client, "আমার বয়স ৬৭, বয়স্ক ভাতা পাবো?")
    assert STUB_SPEECH in xml
    assert messages_bn.CONTINUE in xml
    assert xml.index("<Gather") < xml.index(STUB_SPEECH)  # spoken inside the Gather (barge-in)
    assert call_row(client)["turns"] == 1


def test_answer_is_saved_in_the_shared_history(client: TestClient) -> None:
    turn(client, "বয়স্ক ভাতা")
    history = client.get(f"/api/v1/conversations/{PHONE}").json()
    assert any(STUB_SPEECH in m["text"] for m in history["messages"])


def test_goodbye_phrase_hangs_up(client: TestClient) -> None:
    xml = turn(client, "না, ধন্যবাদ")
    assert messages_bn.GOODBYE in xml
    assert "<Hangup />" in xml
    assert "<Gather" not in xml


def test_sixth_question_is_answered_then_goodbye(client: TestClient) -> None:
    for _ in range(5):
        assert "<Gather" in turn(client, "বয়স্ক ভাতা")
    last = turn(client, "বয়স্ক ভাতা")
    assert STUB_SPEECH in last
    assert messages_bn.GOODBYE in last
    assert messages_bn.CONTINUE not in last
    assert "<Hangup />" in last


def test_engine_failure_speaks_error_and_keeps_listening(client: TestClient) -> None:
    def broken(*_: object) -> None:
        raise LLMUnavailable("key rejected")

    client.app.state.container.answer_engine.answer = broken
    xml = turn(client, "বয়স্ক ভাতা")
    assert messages_bn.ERROR in xml
    assert "<Gather" in xml


# ---------------------------------------------------------------- silence and end


def test_first_silence_reprompts_second_says_goodbye(client: TestClient) -> None:
    first = turn(client)
    assert messages_bn.REPROMPT in first
    assert "<Gather" in first

    second = turn(client, "   ")
    assert messages_bn.GOODBYE in second
    assert "<Hangup />" in second


def test_speech_between_silences_resets_the_count(client: TestClient) -> None:
    turn(client)
    turn(client, "বয়স্ক ভাতা")
    assert messages_bn.REPROMPT in turn(client)


def test_status_completed_stores_the_end_time(client: TestClient) -> None:
    client.post("/voice/incoming", data={"CallSid": "CA1", "From": PHONE, "Direction": "inbound"})
    turn(client)
    response = client.post("/voice/status", data={"CallSid": "CA1", "CallStatus": "completed"})
    assert response.status_code == 204
    assert call_row(client)["ended_at"] is not None
    assert messages_bn.REPROMPT in turn(client)  # the silence count starts fresh


def test_citizen_number_by_direction() -> None:
    assert citizen_number("+8801711111111", "+15005550006", "inbound") == "+8801711111111"
    assert citizen_number("+15005550006", "+8801711111111", "outbound-api") == "+8801711111111"
