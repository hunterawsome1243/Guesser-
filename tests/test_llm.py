import inspect
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app import llm, prompts
from app.llm import ModelError, Turn, next_turn


class FakeClient:
    """Mimics client.beta.messages.create; records the kwargs it was called with."""

    def __init__(self, text=None, stop_reason="end_turn", error=None, content=None):
        self.calls = []
        self._error = error
        self._response = SimpleNamespace(
            stop_reason=stop_reason,
            content=content
            if content is not None
            else [SimpleNamespace(type="thinking", thinking="hmm"), SimpleNamespace(type="text", text=text)],
        )
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def reply(kind, text):
    return json.dumps({"type": kind, "text": text})


def ask(client, history=(), rejected=(), must_guess=False, questions_left=20):
    return next_turn(list(history), list(rejected), must_guess, questions_left, client=client)


def schema_enum(call):
    return call["output_config"]["format"]["schema"]["properties"]["type"]["enum"]


def test_parses_a_question():
    client = FakeClient(reply("question", "  Is it alive?  "))
    assert ask(client) == Turn("question", "Is it alive?")


def test_parses_a_guess():
    client = FakeClient(reply("guess", "a giraffe"))
    assert ask(client) == Turn("guess", "a giraffe")


def test_call_shape():
    client = FakeClient(reply("question", "Is it alive?"))
    ask(client)
    call = client.calls[0]
    assert call["model"] == llm.MODEL
    assert call["max_tokens"] == 16000
    assert call["system"] == prompts.SYSTEM_PROMPT
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"]["effort"] == "medium"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["format"]["schema"]["required"] == ["type", "text"]
    assert call["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["fallbacks"] == "default"
    assert len(call["messages"]) == 1
    assert call["messages"][0]["role"] == "user"
    for banned in ["temperature", "top_p", "tool_choice"]:
        assert banned not in call
    assert schema_enum(call) == ["question", "guess"]


def test_must_guess_only_allows_a_guess():
    client = FakeClient(reply("guess", "a giraffe"))
    ask(client, must_guess=True, questions_left=0)
    call = client.calls[0]
    assert schema_enum(call) == ["guess"]
    assert "You must make your final guess now." in call["messages"][0]["content"]


def test_question_when_a_guess_is_required_is_an_error():
    client = FakeClient(reply("question", "Is it alive?"))
    with pytest.raises(ModelError):
        ask(client, must_guess=True, questions_left=0)


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_early_stop_is_an_error(stop_reason):
    client = FakeClient(reply("question", "Is it alive?"), stop_reason=stop_reason)
    with pytest.raises(ModelError):
        ask(client)


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[1, 2]",
        json.dumps({"type": "question"}),
        json.dumps({"type": "statement", "text": "Hi"}),
        json.dumps({"type": "question", "text": 5}),
        reply("question", ""),
        reply("question", "   "),
    ],
)
def test_bad_replies_are_errors(text):
    with pytest.raises(ModelError):
        ask(FakeClient(text))


def test_missing_text_block_is_an_error():
    client = FakeClient(content=[SimpleNamespace(type="thinking", thinking="hmm")])
    with pytest.raises(ModelError):
        ask(client)


def test_long_text_is_truncated():
    client = FakeClient(reply("question", "x" * 1000))
    assert ask(client).text == "x" * llm.MAX_TEXT_LENGTH


def test_connection_error_becomes_model_error():
    error = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    with pytest.raises(ModelError):
        ask(FakeClient(error=error))


def test_any_exception_becomes_model_error():
    with pytest.raises(ModelError):
        ask(FakeClient(error=RuntimeError("boom")))


def test_client_construction_failure_becomes_model_error():
    # conftest makes _get_client raise, as building a real client would without a key.
    with pytest.raises(ModelError):
        next_turn([], [], False, 20)


def test_message_includes_history_and_rejected_guesses():
    client = FakeClient(reply("question", "Is it big?"))
    history = [
        {"question": "Is it alive?", "answer": "yes"},
        {"question": "Is it a mammal?", "answer": "probably_not"},
        {"question": "Does it fly?", "answer": "dont_know"},
    ]
    ask(client, history=history, rejected=["a giraffe", "a whale"], questions_left=17)
    content = client.calls[0]["messages"][0]["content"]
    assert "1. Q: Is it alive? A: Yes" in content
    assert "2. Q: Is it a mammal? A: Probably not" in content
    assert "3. Q: Does it fly? A: Don't know" in content
    assert "a giraffe" in content and "a whale" in content
    assert "Questions left: 17" in content
    assert "Ask your next question, or guess if you are confident." in content


def test_first_message_says_no_questions_yet():
    client = FakeClient(reply("question", "Is it alive?"))
    ask(client)
    content = client.calls[0]["messages"][0]["content"]
    assert "No questions asked yet." in content
    assert "Rejected" not in content


def test_next_turn_never_takes_the_answer():
    params = list(inspect.signature(next_turn).parameters)
    assert params == ["history", "rejected_guesses", "must_guess", "questions_left", "client"]
