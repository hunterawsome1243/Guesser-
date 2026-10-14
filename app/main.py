"""FastAPI app: serves the page and the game API. Games live in server memory."""

import threading
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import llm
from app.game import Answer, Game, InvalidMove

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
MAX_GAMES = 500
MODEL_ERROR = "The AI couldn't respond just now. Please try again."

app = FastAPI(title="Guesser")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

games: dict[str, Game] = {}  # insertion order = age, so the first key is the oldest
games_lock = threading.Lock()


def get_model():
    """The function used to ask the model. Tests override this with a fake."""
    return llm.next_turn


class AnswerBody(BaseModel):
    answer: Answer


class GuessBody(BaseModel):
    correct: bool


class RevealBody(BaseModel):
    answer: str


@app.exception_handler(RequestValidationError)
def invalid_request(request: Request, exc: RequestValidationError):
    # Keep "detail" a plain string so the page can show it as-is.
    return JSONResponse(status_code=422, content={"detail": "That request wasn't valid."})


def save_game(game: Game) -> None:
    with games_lock:
        games[game.game_id] = game
        while len(games) > MAX_GAMES:
            del games[next(iter(games))]


def find_game(game_id: str) -> Game:
    with games_lock:
        game = games.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found.")
    return game


@contextmanager
def playing(game_id: str):
    """Lock one game for a move and turn game errors into HTTP errors."""
    game = find_game(game_id)
    if not game.lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Still working on your last answer.")
    try:
        yield game
    except InvalidMove as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except llm.ModelError:
        raise HTTPException(status_code=502, detail=MODEL_ERROR)
    finally:
        game.lock.release()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index():
    page = STATIC_DIR / "index.html"
    if not page.is_file():
        raise HTTPException(status_code=404, detail="Page not found.")
    return FileResponse(page)


@app.post("/api/games")
def start_game(model=Depends(get_model)):
    try:
        game = Game.start(model)
    except llm.ModelError:
        raise HTTPException(status_code=502, detail=MODEL_ERROR)
    save_game(game)
    return game.to_dict()


@app.get("/api/games/{game_id}")
def get_game(game_id: str):
    return find_game(game_id).to_dict()


@app.post("/api/games/{game_id}/answer")
def answer(game_id: str, body: AnswerBody, model=Depends(get_model)):
    with playing(game_id) as game:
        game.answer(body.answer, model)
        return game.to_dict()


@app.post("/api/games/{game_id}/guess")
def guess(game_id: str, body: GuessBody, model=Depends(get_model)):
    with playing(game_id) as game:
        if body.correct:
            game.correct_guess()
        else:
            game.wrong_guess(model)
        return game.to_dict()


@app.post("/api/games/{game_id}/undo")
def undo(game_id: str):
    with playing(game_id) as game:
        game.undo()
        return game.to_dict()


@app.post("/api/games/{game_id}/reveal")
def reveal(game_id: str, body: RevealBody):
    with playing(game_id) as game:
        game.reveal(body.answer)
        return game.to_dict()
