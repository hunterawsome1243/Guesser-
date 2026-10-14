"""Asks the Anthropic model for its next move: a question or a guess.

Run `python -m app.llm` to print a first question (needs ANTHROPIC_API_KEY).
"""

import json
import logging
import os
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv

from app import prompts

load_dotenv()

log = logging.getLogger(__name__)

MODEL = os.getenv("GUESSER_MODEL", "claude-opus-5-5")
MAX_TEXT_LENGTH = 300

_client = None


@dataclass
class Turn:
    kind: str  # "question" or "guess"
    text: str


class ModelError(Exception):
    """The model could not be reached or gave an unusable reply."""


def _get_client():
    """Build the API client on first use, so importing this module never needs a key."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(timeout=60.0, max_retries=2)
    return _client


def next_turn(history, rejected_guesses, must_guess, questions_left, client=None) -> Turn:
    """Return the model's next question or guess. Raises ModelError on any failure."""
    allowed = ["guess"] if must_guess else ["question", "guess"]
    schema = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": allowed},
            "text": {"type": "string"},
        },
        "required": ["type", "text"],
        "additionalProperties": False,
    }
    message = prompts.build_turn_message(history, rejected_guesses, must_guess, questions_left)

    try:
        client = client or _get_client()
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=prompts.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
            thinking={"type": "adaptive"},
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as exc:
        log.error("Anthropic API error: %s", exc)
        raise ModelError("The model call failed.") from exc
    except Exception as exc:
        log.exception("Unexpected error while calling the model")
        raise ModelError("The model call failed.") from exc

    return _parse(response, allowed)


def _parse(response, allowed) -> Turn:
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason in ("refusal", "max_tokens"):
        log.error("Model stopped early: stop_reason=%s", stop_reason)
        raise ModelError(f"The model stopped early ({stop_reason}).")

    text = next(
        (block.text for block in getattr(response, "content", None) or [] if getattr(block, "type", None) == "text"),
        None,
    )
    if text is None:
        log.error("Model reply had no text block")
        raise ModelError("The model reply had no text.")

    try:
        data = json.loads(text)
    except (TypeError, ValueError) as exc:
        log.error("Model reply was not valid JSON: %r", text[:500])
        raise ModelError("The model reply was not valid JSON.") from exc

    kind = data.get("type") if isinstance(data, dict) else None
    body = data.get("text") if isinstance(data, dict) else None
    if kind not in allowed or not isinstance(body, str) or not body.strip():
        log.error("Model reply did not match the expected shape: %r", text[:500])
        raise ModelError("The model reply did not match the expected shape.")

    return Turn(kind=kind, text=body.strip()[:MAX_TEXT_LENGTH])


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. Put it in .env (see .env.example) or export it.")
    logging.basicConfig(level=logging.INFO)
    try:
        turn = next_turn(history=[], rejected_guesses=[], must_guess=False, questions_left=20)
    except ModelError as error:
        raise SystemExit(f"Model call failed: {error} (check ANTHROPIC_API_KEY, GUESSER_MODEL and the log above)")
    print(f"{turn.kind}: {turn.text}")
