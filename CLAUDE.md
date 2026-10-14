# Guesser

Guesser is a web-based 20-questions style game where an AI asks yes/no questions to work out whatever you are thinking of, aiming to name it in as few guesses as possible.

## About this project
- **Who it is for:** Casual players who enjoy Akinator-style games and want one that can handle any topic, plus friends or families playing for fun.
- **Problem it solves:** Existing guessing games rely on a fixed database of characters, so they fail when you think of something obscure or unusual. Guesser uses a language model to reason about any answer, so there is no fixed list of things it can guess.
- **Done when:** A player opens the web page, thinks of anything, and answers yes/no/maybe questions asked by the AI. The AI makes a final guess within a set question limit, the player says whether it was right, and can start a new game.

## Tech stack
- Python 3.11+
- FastAPI for the backend
- Anthropic Python SDK for the language model calls
- Plain HTML, CSS and JavaScript for the frontend (no framework)
- pytest for tests
- python-dotenv for loading the API key

## Commands
```sh
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn anthropic python-dotenv pytest httpx
uvicorn app.main:app --reload
pytest
```

## Conventions
- Keep the code simple and in as few files as possible; prefer well-known libraries over clever solutions.
- Never hard-code the API key; read ANTHROPIC_API_KEY from the environment or a .env file that is git-ignored.
- After each task, run the tests and start the app to confirm it still works before finishing.
- Keep model prompts in one separate file so they are easy to read and edit.
- Explain in plain language what you changed and how to try it at the end of each task.

## Constraints
- The model must never be told the answer, since the game is the AI deducing it. Each game costs API calls, so cap the number of questions and keep conversation history compact. Keep the API key on the server only, never in browser code.

## First version (must have)
- Question loop: The AI asks one yes/no question at a time and the player answers Yes, No, Probably, Probably not, or Don't know.
- Final guess: When the AI is confident or reaches the question limit, it names a specific thing as its guess.
- Win or lose result: The player confirms whether the guess was correct and sees a result screen.
- Simple web interface: A single page with a start button, the current question, answer buttons, and a question counter.
- Play again: After a game ends, the player can start a fresh game with one click.

## After the first version (should have)
- Wrong-guess recovery: If the guess is wrong, the AI continues asking questions and tries again, up to a limited number of guesses.
- Ask for the answer on loss: If the AI gives up, it asks what the player was thinking of and shows it on the result screen.
- Smart question strategy: The prompt guides the AI to start with broad questions (living or not, size, category) and narrow down efficiently.

## How to work in this repo
- The plan is in PLAN.md, and its top says how to use it. When a task works, tick it there: "- [ ]" becomes "- [x]", and "(S)" becomes "(S, done YYYY-MM-DD)" with today's date.
- Read the files a task touches before changing them.
- Tasks marked (S) and small fixes: go ahead. Anything bigger: outline the plan first and wait for a go-ahead.
- Keep changes small. After each step run the tests from Commands and fix failures before moving on. A check that is not set up yet (a later task adds it) is not a failure: say so and go on.
- Ask before adding a new dependency or changing the tech stack.
