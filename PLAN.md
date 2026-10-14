# Plan: Guesser

Guesser is a web-based 20-questions style game where an AI asks yes/no questions to work out whatever you are thinking of, aiming to name it in as few guesses as possible.

How to use this file:
- Fix any unchecked blocker under "Bugs to fix" first. Then take the first unchecked task under a "Milestone" heading, in the first milestone that still has one.
- When a task or bug works and its checks pass, change its "- [ ]" to "- [x]". On a task, also add today's date to its brackets: "(S)" becomes "(S, done YYYY-MM-DD)".
- Keep the hidden id comment at the end of each line. Do not reorder, rename or delete lines.
- A large (L) task can be split into steps: indented "- [ ]" lines under it, done in order. Tick the task itself only when all its steps are ticked.
- Put anything worth remembering on an indented "Notes:" line under the task. If you find extra work that is needed, add it as a new "- [ ]" line in the milestone it belongs to: just above the task that needs it done first, otherwise at the end.

## Milestone 1: Bare-bones game running

Goal: A player can play one full game in the terminal-launched local web server using a minimal page.

- [ ] Set up the project skeleton (S) <!-- id:t1lfmi6ag8le -->
  Notes: Create the folder structure, virtual environment, requirements.txt, .gitignore including .env, and a FastAPI app with a /health endpoint. Check by running uvicorn and opening /health.
- [ ] Add a function that asks the model for the next question (M) <!-- id:tgal6v88g8le -->
  Notes: Write a function that takes the list of questions and answers so far and calls the Anthropic API to return the next yes/no question. Check with a small script that prints a question.
- [ ] Create the game API endpoints (M) <!-- id:tfeyp5cjg8lf -->
  Notes: Add endpoints to start a game and submit an answer, keeping game state in server memory by game ID. Check using curl or the FastAPI /docs page.
- [ ] Build a minimal HTML page for playing (M) <!-- id:tnbeyfpxg8lf -->
  Notes: Serve one page with a start button, the question text, and answer buttons that call the API. Check by playing a few rounds in the browser.

## Milestone 2: Complete game flow

Goal: A game reliably ends with a guess and a confirmed win or loss, and can be replayed.

- [ ] Let the model decide between asking and guessing (M) <!-- id:tylz99g3g8lf -->
  Notes: Change the model output to a structured JSON reply of either a question or a guess, and parse it safely. Add tests with mocked model replies for both cases.
- [ ] Add a question limit that forces a guess (S) <!-- id:ten9amgag8lf -->
  Notes: After a set number of questions (for example 20), instruct the model to make its best guess. Check with a test that uses a mocked model.
- [ ] Add the guess confirmation and result screen (M) <!-- id:tb6nhb0ag8lf -->
  Notes: Show the guess with Correct and Wrong buttons, then a result screen with the number of questions used. Check by playing to the end in the browser.
- [ ] Add a Play again button (S) <!-- id:tq8pu41mg8lf -->
  Notes: Reset the page state and start a new game from the result screen. Check that a second game does not reuse old answers.

## Milestone 3: Smarter and more forgiving play

Goal: The AI asks better questions and recovers from wrong guesses.

- [ ] Write a better strategy prompt (M) <!-- id:th009imrg8lf -->
  Notes: Move the prompt to its own file and add guidance for broad-to-narrow questions, avoiding repeats, and handling Probably and Don't know. Check by playing three games with different kinds of things.
- [ ] Continue after a wrong guess (M) <!-- id:tj83oweng8lf -->
  Notes: On a wrong guess, tell the model which guesses were rejected and keep going, with a cap of three guesses. Check with a mocked test and a manual game.
- [ ] Ask what the player was thinking of when the AI loses (S) <!-- id:t8q6wbp7g8lf -->
  Notes: After the final failure, show a text box and display the entered answer on the result screen. Check manually.

## Milestone 4: Polish and extras

Goal: The game looks decent, handles errors gracefully, and has optional extras.

- [ ] Handle API errors and timeouts (M) <!-- id:tgdnaknsg8lf -->
  Notes: Show a friendly message and a retry button if the model call fails. Check by temporarily using a bad API key.
- [ ] Style the page (M) <!-- id:t99q0jgpg8lf -->
  Notes: Add CSS for a clean, mobile-friendly layout with clear answer buttons and a progress counter. Check on a narrow browser window.
- [ ] Add an undo button (M) <!-- id:tgansxbwg8lf -->
  Notes: Let the player remove the last answer and get the previous question again. Check that the question counter goes back by one.
- [ ] Save simple stats in the browser (S) <!-- id:twm0u21kg8lf -->
  Notes: Store games played, wins, and average questions in localStorage and show them on the start screen. Check that they persist after a reload.
- [ ] Write a README with setup and play instructions (S) <!-- id:tiyruj9vg8lf -->
  Notes: Document how to get an API key, install, run, and test. Check by following the steps from a clean checkout.
