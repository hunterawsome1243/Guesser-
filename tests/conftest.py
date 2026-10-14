import copy

import pytest
from fastapi.testclient import TestClient

from app import llm, main
from app.llm import ModelError, Turn


class FakeModel:
    """Stands in for llm.next_turn. Records every call; never touches the network.

    By default it asks "Question N?" (N = answers so far + 1) and guesses
    "guess K" when it must. Queue replies in `replies`, or set `failures`
    to make the next calls raise ModelError.
    """

    def __init__(self):
        self.calls = []
        self.replies = []
        self.failures = 0

    def __call__(self, history, rejected_guesses, must_guess, questions_left):
        self.calls.append(
            {
                "history": copy.deepcopy(history),
                "rejected_guesses": list(rejected_guesses),
                "must_guess": must_guess,
                "questions_left": questions_left,
            }
        )
        if self.failures:
            self.failures -= 1
            raise ModelError("fake failure")
        if self.replies:
            return self.replies.pop(0)
        if must_guess:
            return Turn("guess", f"guess {len(rejected_guesses) + 1}")
        return Turn("question", f"Question {len(history) + 1}?")

    def queue_guess(self, text):
        self.replies.append(Turn("guess", text))


@pytest.fixture(autouse=True)
def no_real_client(monkeypatch):
    """Make sure no test can ever build the real Anthropic client."""

    def refuse():
        raise RuntimeError("Tests must not call the real Anthropic API.")

    monkeypatch.setattr(llm, "_get_client", refuse)


@pytest.fixture
def fake_model():
    return FakeModel()


@pytest.fixture
def client(fake_model):
    main.app.dependency_overrides[main.get_model] = lambda: fake_model
    main.games.clear()
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
    main.games.clear()
