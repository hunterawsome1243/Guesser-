# Guesser

Guesser is a 20-questions game in your browser. You think of anything at all (an animal, an object, a person, a character, a place) and an AI asks you yes/no questions to work out what it is. You answer Yes, No, Probably, Probably not or Don't know. When the AI is confident, or runs out of questions, it makes a guess and you tell it whether it was right.

## What you need

- Python 3.11 or newer
- An Anthropic API key

## Get an API key

1. Sign in at [console.anthropic.com](https://console.anthropic.com/).
2. Open **API Keys** and create a key.
3. In this folder, copy the example settings file and put your key in it:

   ```sh
   cp .env.example .env
   ```

   Then edit `.env` so it reads `ANTHROPIC_API_KEY=sk-ant-...` with your key.

`.env` is git-ignored, so your key is never committed. The key stays on the server and is never sent to the browser.

## Install

```sh
python3 -m venv .venv            # On Windows: py -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```sh
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and click **Start**.

To check that your key works without opening the browser, run `python -m app.llm`. It prints the AI's first question.

### Choosing a model (optional)

The game uses `claude-opus-5-5` by default. To use a different Claude model, add a line like this to `.env` (or set it in your shell):

```sh
GUESSER_MODEL=claude-sonnet-5-5
```

The model must support adaptive thinking, the effort setting and structured outputs, for example `claude-sonnet-5-5` or `claude-haiku-5-5`. Older models such as `claude-haiku-4-5` reject the request, and the page then keeps showing the "couldn't respond" error however often you retry.

### Troubleshooting

If the page keeps saying "The AI couldn't respond just now. Please try again." and **Retry** never helps, look at the terminal running uvicorn, which shows the real error. A 401 or `authentication_error` means `ANTHROPIC_API_KEY` in `.env` is missing, wrong or still the placeholder from `.env.example`. A 400 that mentions the model or a setting usually means `GUESSER_MODEL` names an unsupported model (see above). `python -m app.llm` shows the same error without the browser.

## Test

```sh
pytest
```

The tests use a fake model, so they need no API key and make no network calls.

## How it works

The browser only talks to this app's own `/api/...` endpoints. The server keeps each game in memory and asks the model for its next move: either a question or a guess. The model is never told the answer, not even after you reveal it at the end, because the whole point is for it to work it out. To keep each request small, the questions and answers so far are sent as one short numbered list, not as a growing chat. Each game is capped at 20 questions and 3 guesses. After 20 questions the model must guess. If a guess is wrong, it keeps asking until it has used all 3 guesses. If the model can't be reached, the page shows a message and a **Retry** button, and the game carries on from where it was. Games played, wins and average questions are saved in your browser.

## Project layout

- `app/main.py`: web server, game API and page serving (FastAPI)
- `app/game.py`: game rules and state (question and guess limits, undo, win or loss)
- `app/llm.py`: the call to the Anthropic API and checks on the model's reply
- `app/prompts.py`: all text sent to the model
- `static/`: the web page (`index.html`, `style.css`, `app.js`)
- `tests/`: pytest tests for the game, the API and the model call
- `requirements.txt`: Python packages
- `.env.example`: template for your `.env` file
