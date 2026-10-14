"""Game state and rules. No web framework and no network here.

Moves that need the model take an `ask` function (normally llm.next_turn).
The game only changes after `ask` returns, so if the model fails the state
stays exactly as it was and the same move can simply be retried.
"""

import threading
import uuid
from dataclasses import dataclass, field
from typing import Literal, get_args

MAX_QUESTIONS = 20
MAX_GUESSES = 3
MAX_REVEAL_LENGTH = 200

Answer = Literal["yes", "no", "probably", "probably_not", "dont_know"]
ANSWERS = get_args(Answer)


class InvalidMove(Exception):
    """The move is not allowed in the game's current status."""


def _ask(ask, history, rejected_guesses):
    asked = len(history)
    return ask(
        history=[dict(item) for item in history],
        rejected_guesses=list(rejected_guesses),
        must_guess=asked >= MAX_QUESTIONS,
        questions_left=max(0, MAX_QUESTIONS - asked),
    )


@dataclass
class Game:
    game_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "question"  # "question", "guess", "won" or "lost"
    question: str | None = None
    guess: str | None = None
    history: list = field(default_factory=list)  # [{"question": str, "answer": str}]
    rejected_guesses: list = field(default_factory=list)
    undo_floor: int = 0  # len(history) at the most recent rejected guess
    revealed_answer: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @classmethod
    def start(cls, ask) -> "Game":
        turn = _ask(ask, [], [])
        game = cls()
        game._show(turn)
        return game

    @property
    def can_undo(self) -> bool:
        return self.status in ("question", "guess") and len(self.history) > self.undo_floor

    def answer(self, answer: str, ask) -> None:
        self._require("question", "There's no question waiting for an answer.")
        if answer not in ANSWERS:
            raise ValueError(f"Unknown answer: {answer!r}")
        history = self.history + [{"question": self.question, "answer": answer}]
        turn = _ask(ask, history, self.rejected_guesses)
        self.history = history
        self._show(turn)

    def correct_guess(self) -> None:
        self._require("guess", "There's no guess to confirm.")
        self.status = "won"

    def wrong_guess(self, ask) -> None:
        self._require("guess", "There's no guess to reject.")
        rejected = self.rejected_guesses + [self.guess]
        if len(rejected) >= MAX_GUESSES:
            self.rejected_guesses = rejected
            self.undo_floor = len(self.history)
            self.guess = None
            self.status = "lost"
            return
        turn = _ask(ask, self.history, rejected)
        self.rejected_guesses = rejected
        self.undo_floor = len(self.history)
        self._show(turn)

    def undo(self) -> None:
        if not self.can_undo:
            raise InvalidMove("There's nothing to undo.")
        last = self.history[-1]
        self.history = self.history[:-1]
        self.question = last["question"]
        self.guess = None
        self.status = "question"

    def reveal(self, text: str) -> None:
        self._require("lost", "You can only tell me the answer after I give up.")
        text = text.strip()
        if not 1 <= len(text) <= MAX_REVEAL_LENGTH:
            raise ValueError(f"Please type between 1 and {MAX_REVEAL_LENGTH} characters.")
        self.revealed_answer = text

    def to_dict(self) -> dict:
        showing_guess = self.status in ("guess", "won")
        return {
            "game_id": self.game_id,
            "status": self.status,
            "question": self.question if self.status == "question" else None,
            "guess": self.guess if showing_guess else None,
            "questions_asked": len(self.history),
            "max_questions": MAX_QUESTIONS,
            "guesses_made": len(self.rejected_guesses) + (1 if showing_guess else 0),
            "max_guesses": MAX_GUESSES,
            "rejected_guesses": list(self.rejected_guesses),
            "can_undo": self.can_undo,
            "revealed_answer": self.revealed_answer,
        }

    def _require(self, status: str, message: str) -> None:
        if self.status != status:
            raise InvalidMove(message)

    def _show(self, turn) -> None:
        if turn.kind == "guess":
            self.status, self.guess, self.question = "guess", turn.text, None
        else:
            self.status, self.question, self.guess = "question", turn.text, None
