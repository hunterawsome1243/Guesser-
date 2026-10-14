import pytest

from app.game import MAX_GUESSES, MAX_QUESTIONS, Game, InvalidMove
from app.llm import ModelError, Turn


def answer_n(game, model, n, answer="no"):
    for _ in range(n):
        game.answer(answer, model)


def test_start_asks_first_question(fake_model):
    game = Game.start(fake_model)
    assert game.status == "question"
    assert game.question == "Question 1?"
    assert len(game.game_id) == 32
    assert fake_model.calls == [
        {"history": [], "rejected_guesses": [], "must_guess": False, "questions_left": MAX_QUESTIONS}
    ]


def test_answering_moves_forward(fake_model):
    game = Game.start(fake_model)
    game.answer("yes", fake_model)
    assert game.question == "Question 2?"
    assert game.history == [{"question": "Question 1?", "answer": "yes"}]
    assert fake_model.calls[-1]["history"] == game.history
    assert fake_model.calls[-1]["questions_left"] == MAX_QUESTIONS - 1
    assert game.to_dict()["questions_asked"] == 1


def test_unknown_answer_value_is_rejected(fake_model):
    game = Game.start(fake_model)
    with pytest.raises(ValueError):
        game.answer("maybe", fake_model)
    assert game.history == []


def test_answer_only_allowed_when_a_question_is_waiting(fake_model):
    fake_model.queue_guess("a cat")
    game = Game.start(fake_model)
    with pytest.raises(InvalidMove):
        game.answer("yes", fake_model)


def test_forced_guess_at_question_limit(fake_model):
    game = Game.start(fake_model)
    answer_n(game, fake_model, MAX_QUESTIONS - 1)
    assert fake_model.calls[-1]["must_guess"] is False
    assert fake_model.calls[-1]["questions_left"] == 1
    assert game.status == "question"

    game.answer("no", fake_model)
    assert fake_model.calls[-1]["must_guess"] is True
    assert fake_model.calls[-1]["questions_left"] == 0
    assert game.status == "guess"
    assert game.to_dict()["questions_asked"] == MAX_QUESTIONS


def test_correct_guess_wins_and_keeps_the_guess(fake_model):
    game = Game.start(fake_model)
    fake_model.queue_guess("a giraffe")
    game.answer("yes", fake_model)
    assert game.status == "guess"
    game.correct_guess()
    state = game.to_dict()
    assert state["status"] == "won"
    assert state["guess"] == "a giraffe"
    assert state["guesses_made"] == 1
    assert state["can_undo"] is False


def test_wrong_guess_continues_with_rejected_guess(fake_model):
    game = Game.start(fake_model)
    fake_model.queue_guess("a giraffe")
    game.answer("yes", fake_model)
    game.wrong_guess(fake_model)
    assert game.status == "question"
    assert game.rejected_guesses == ["a giraffe"]
    assert fake_model.calls[-1]["rejected_guesses"] == ["a giraffe"]
    assert fake_model.calls[-1]["must_guess"] is False
    state = game.to_dict()
    assert state["guess"] is None
    assert state["guesses_made"] == 1


def test_wrong_guess_at_question_limit_forces_another_guess(fake_model):
    game = Game.start(fake_model)
    answer_n(game, fake_model, MAX_QUESTIONS)
    assert game.guess == "guess 1"
    game.wrong_guess(fake_model)
    assert fake_model.calls[-1]["must_guess"] is True
    assert game.status == "guess"
    assert game.guess == "guess 2"
    assert game.to_dict()["guesses_made"] == 2


def test_third_wrong_guess_loses_without_calling_the_model(fake_model):
    game = Game.start(fake_model)
    answer_n(game, fake_model, MAX_QUESTIONS)
    game.wrong_guess(fake_model)
    game.wrong_guess(fake_model)
    calls_before = len(fake_model.calls)
    game.wrong_guess(fake_model)
    assert len(fake_model.calls) == calls_before
    state = game.to_dict()
    assert state["status"] == "lost"
    assert state["rejected_guesses"] == ["guess 1", "guess 2", "guess 3"]
    assert state["guesses_made"] == MAX_GUESSES
    assert state["guess"] is None
    assert state["can_undo"] is False


def test_guess_moves_need_a_guess(fake_model):
    game = Game.start(fake_model)
    with pytest.raises(InvalidMove):
        game.correct_guess()
    with pytest.raises(InvalidMove):
        game.wrong_guess(fake_model)


def test_undo_restores_previous_question(fake_model):
    game = Game.start(fake_model)
    answer_n(game, fake_model, 2)
    calls_before = len(fake_model.calls)
    game.undo()
    assert len(fake_model.calls) == calls_before
    assert game.status == "question"
    assert game.question == "Question 2?"
    assert game.to_dict()["questions_asked"] == 1


def test_undo_from_a_guess(fake_model):
    game = Game.start(fake_model)
    fake_model.queue_guess("a giraffe")
    game.answer("yes", fake_model)
    game.undo()
    state = game.to_dict()
    assert state["status"] == "question"
    assert state["question"] == "Question 1?"
    assert state["guess"] is None
    assert state["questions_asked"] == 0


def test_undo_blocked_when_history_is_empty(fake_model):
    game = Game.start(fake_model)
    assert game.can_undo is False
    with pytest.raises(InvalidMove):
        game.undo()


def test_undo_blocked_right_after_a_rejected_guess(fake_model):
    game = Game.start(fake_model)
    game.answer("yes", fake_model)
    fake_model.queue_guess("a giraffe")
    game.answer("yes", fake_model)
    game.wrong_guess(fake_model)
    assert game.can_undo is False
    with pytest.raises(InvalidMove):
        game.undo()

    game.answer("no", fake_model)
    assert game.can_undo is True
    game.undo()
    assert game.can_undo is False
    assert game.to_dict()["questions_asked"] == 2


def test_reveal_only_when_lost(fake_model):
    game = Game.start(fake_model)
    with pytest.raises(InvalidMove):
        game.reveal("a teapot")
    fake_model.replies = [Turn("guess", "a cat"), Turn("guess", "a dog"), Turn("guess", "a cow")]
    game.answer("yes", fake_model)
    for _ in range(MAX_GUESSES):
        game.wrong_guess(fake_model)
    assert game.status == "lost"
    game.reveal("  a teapot  ")
    assert game.to_dict()["revealed_answer"] == "a teapot"


def test_reveal_length_limits(fake_model):
    game = Game(status="lost", rejected_guesses=["a", "b", "c"])
    for bad in ["", "   ", "x" * 201]:
        with pytest.raises(ValueError):
            game.reveal(bad)
        assert game.revealed_answer is None
    game.reveal("x" * 200)
    assert game.revealed_answer == "x" * 200
    game.reveal(" y ")
    assert game.revealed_answer == "y"


def test_model_failure_leaves_state_unchanged(fake_model):
    game = Game.start(fake_model)
    game.answer("yes", fake_model)
    before = game.to_dict()

    fake_model.failures = 1
    with pytest.raises(ModelError):
        game.answer("no", fake_model)
    assert game.to_dict() == before

    fake_model.replies.append(Turn("guess", "a giraffe"))
    game.answer("no", fake_model)
    before = game.to_dict()
    fake_model.failures = 1
    with pytest.raises(ModelError):
        game.wrong_guess(fake_model)
    assert game.to_dict() == before


def test_to_dict_shape(fake_model):
    game = Game.start(fake_model)
    state = game.to_dict()
    assert state == {
        "game_id": game.game_id,
        "status": "question",
        "question": "Question 1?",
        "guess": None,
        "questions_asked": 0,
        "max_questions": 20,
        "guesses_made": 0,
        "max_guesses": 3,
        "rejected_guesses": [],
        "can_undo": False,
        "revealed_answer": None,
    }
