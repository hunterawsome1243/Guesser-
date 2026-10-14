import pytest

from app import main
from app.llm import Turn


def start(client):
    response = client.post("/api/games")
    assert response.status_code == 200
    return response.json()


def answer(client, game_id, value="yes"):
    return client.post(f"/api/games/{game_id}/answer", json={"answer": value})


def guess(client, game_id, correct):
    return client.post(f"/api/games/{game_id}/guess", json={"correct": correct})


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_start_game(client, fake_model):
    state = start(client)
    assert state["status"] == "question"
    assert state["question"] == "Question 1?"
    assert state["questions_asked"] == 0
    assert state["max_questions"] == 20
    assert state["max_guesses"] == 3
    assert state["can_undo"] is False
    assert len(fake_model.calls) == 1
    assert client.get(f"/api/games/{state['game_id']}").json() == state


def test_answer_gives_next_question(client, fake_model):
    game_id = start(client)["game_id"]
    response = answer(client, game_id, "probably_not")
    assert response.status_code == 200
    state = response.json()
    assert state["question"] == "Question 2?"
    assert state["questions_asked"] == 1
    assert state["can_undo"] is True
    assert fake_model.calls[-1]["history"] == [{"question": "Question 1?", "answer": "probably_not"}]


def test_all_answer_values_accepted(client):
    game_id = start(client)["game_id"]
    for value in ["yes", "no", "probably", "probably_not", "dont_know"]:
        assert answer(client, game_id, value).status_code == 200


def test_must_guess_after_twenty_answers(client, fake_model):
    game_id = start(client)["game_id"]
    for _ in range(19):
        state = answer(client, game_id, "no").json()
    assert fake_model.calls[-1]["must_guess"] is False
    assert state["status"] == "question"

    state = answer(client, game_id, "no").json()
    assert fake_model.calls[-1]["must_guess"] is True
    assert fake_model.calls[-1]["questions_left"] == 0
    assert state["status"] == "guess"
    assert state["questions_asked"] == 20
    assert state["guess"] == "guess 1"


def test_correct_guess_wins(client, fake_model):
    game_id = start(client)["game_id"]
    fake_model.queue_guess("a giraffe")
    state = answer(client, game_id).json()
    assert state["status"] == "guess"
    assert state["guess"] == "a giraffe"
    assert state["guesses_made"] == 1

    state = guess(client, game_id, True).json()
    assert state["status"] == "won"
    assert state["guess"] == "a giraffe"
    assert state["questions_asked"] == 1


def test_wrong_guess_continues(client, fake_model):
    game_id = start(client)["game_id"]
    fake_model.queue_guess("a giraffe")
    answer(client, game_id)
    state = guess(client, game_id, False).json()
    assert state["status"] == "question"
    assert state["rejected_guesses"] == ["a giraffe"]
    assert state["guess"] is None
    assert state["can_undo"] is False
    assert fake_model.calls[-1]["rejected_guesses"] == ["a giraffe"]


def test_lost_after_three_wrong_guesses_then_reveal(client, fake_model):
    game_id = start(client)["game_id"]
    for name in ["a cat", "a dog", "a cow"]:
        fake_model.queue_guess(name)
        assert answer(client, game_id).status_code == 200
        state = guess(client, game_id, False).json()
    assert state["status"] == "lost"
    assert state["rejected_guesses"] == ["a cat", "a dog", "a cow"]
    assert state["guesses_made"] == 3

    calls_before = len(fake_model.calls)
    response = client.post(f"/api/games/{game_id}/reveal", json={"answer": "  a teapot "})
    assert response.status_code == 200
    assert response.json()["revealed_answer"] == "a teapot"
    assert len(fake_model.calls) == calls_before
    # The answer is never sent to the model.
    assert all("teapot" not in str(call) for call in fake_model.calls)


def test_reveal_rejects_bad_text(client, fake_model):
    game_id = start(client)["game_id"]
    for _ in range(3):
        fake_model.queue_guess("a cat")
        answer(client, game_id)
        guess(client, game_id, False)
    for bad in ["   ", "x" * 201]:
        response = client.post(f"/api/games/{game_id}/reveal", json={"answer": bad})
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], str)


def test_reveal_not_allowed_before_losing(client):
    game_id = start(client)["game_id"]
    response = client.post(f"/api/games/{game_id}/reveal", json={"answer": "a teapot"})
    assert response.status_code == 409


def test_undo(client, fake_model):
    game_id = start(client)["game_id"]
    answer(client, game_id)
    answer(client, game_id)
    calls_before = len(fake_model.calls)
    response = client.post(f"/api/games/{game_id}/undo")
    assert response.status_code == 200
    state = response.json()
    assert state["question"] == "Question 2?"
    assert state["questions_asked"] == 1
    assert len(fake_model.calls) == calls_before


def test_undo_not_allowed_at_start(client):
    game_id = start(client)["game_id"]
    response = client.post(f"/api/games/{game_id}/undo")
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)


def test_unknown_game_is_404(client):
    assert client.get("/api/games/nope").status_code == 404
    response = answer(client, "nope")
    assert response.status_code == 404
    assert response.json() == {"detail": "Game not found."}
    assert client.post("/api/games/nope/undo").status_code == 404


def test_wrong_status_is_409(client):
    game_id = start(client)["game_id"]
    response = guess(client, game_id, True)
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)


def test_bad_answer_value_is_422(client):
    game_id = start(client)["game_id"]
    response = answer(client, game_id, "maybe")
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert client.post(f"/api/games/{game_id}/answer", json={}).status_code == 422


def test_busy_game_is_409(client):
    game_id = start(client)["game_id"]
    game = main.games[game_id]
    game.lock.acquire()
    try:
        response = answer(client, game_id)
    finally:
        game.lock.release()
    assert response.status_code == 409
    assert response.json() == {"detail": "Still working on your last answer."}
    assert answer(client, game_id).status_code == 200


def test_model_failure_on_start_is_502_and_stores_nothing(client, fake_model):
    fake_model.failures = 1
    response = client.post("/api/games")
    assert response.status_code == 502
    assert response.json() == {"detail": "The AI couldn't respond just now. Please try again."}
    assert main.games == {}
    assert start(client)["status"] == "question"


def test_model_failure_on_answer_keeps_state_and_retry_works(client, fake_model):
    game_id = start(client)["game_id"]
    answer(client, game_id, "yes")
    before = client.get(f"/api/games/{game_id}").json()

    fake_model.failures = 1
    response = answer(client, game_id, "no")
    assert response.status_code == 502
    assert response.json() == {"detail": "The AI couldn't respond just now. Please try again."}
    assert client.get(f"/api/games/{game_id}").json() == before

    response = answer(client, game_id, "no")
    assert response.status_code == 200
    state = response.json()
    assert state["questions_asked"] == 2
    assert fake_model.calls[-1]["history"] == [
        {"question": "Question 1?", "answer": "yes"},
        {"question": "Question 2?", "answer": "no"},
    ]


def test_model_failure_on_wrong_guess_keeps_state_and_retry_works(client, fake_model):
    game_id = start(client)["game_id"]
    fake_model.queue_guess("a giraffe")
    answer(client, game_id)
    before = client.get(f"/api/games/{game_id}").json()

    fake_model.failures = 1
    assert guess(client, game_id, False).status_code == 502
    assert client.get(f"/api/games/{game_id}").json() == before

    state = guess(client, game_id, False).json()
    assert state["status"] == "question"
    assert state["rejected_guesses"] == ["a giraffe"]


def test_second_game_does_not_share_history(client, fake_model):
    first = start(client)["game_id"]
    answer(client, first, "yes")
    answer(client, first, "no")

    second = start(client)
    assert second["game_id"] != first
    assert second["questions_asked"] == 0
    assert fake_model.calls[-1]["history"] == []
    answer(client, second["game_id"], "dont_know")
    assert fake_model.calls[-1]["history"] == [{"question": "Question 1?", "answer": "dont_know"}]
    assert client.get(f"/api/games/{first}").json()["questions_asked"] == 2


def test_oldest_games_are_evicted(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_GAMES", 2)
    ids = [start(client)["game_id"] for _ in range(3)]
    assert client.get(f"/api/games/{ids[0]}").status_code == 404
    assert client.get(f"/api/games/{ids[2]}").status_code == 200


def test_index_serves_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.parametrize("path", ["/static/app.js", "/static/style.css"])
def test_static_files_are_served(client, path):
    assert client.get(path).status_code == 200
