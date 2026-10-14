// Guesser frontend: one small state object, one render(state) function,
// and one request() helper that handles loading, errors and Retry.
// The browser only talks to /api/*; it never sees an API key or calls a model.
"use strict";

const STATS_KEY = "guesser-stats";

const state = {
  game: null,        // latest game state from the server, or null on the start screen
  loading: false,    // true while a request is in flight
  error: null,       // { message, retry, restart } or null
  lastRequest: null, // { method, path, body } so Retry can resend exactly the failed request
};

const recordedGames = new Set(); // game_ids already counted in the stats
let keyboardUser = false;        // only move focus for people navigating by keyboard

const $ = (id) => document.getElementById(id);

// ---------- Stats in localStorage (the page still works if storage is blocked) ----------

function loadStats() {
  try {
    const stats = JSON.parse(localStorage.getItem(STATS_KEY));
    if (stats && [stats.played, stats.wins, stats.totalQuestions].every(Number.isFinite)) {
      return stats;
    }
  } catch {
    // Storage blocked or corrupt: fall through to empty stats.
  }
  return { played: 0, wins: 0, totalQuestions: 0 };
}

function saveStats(stats) {
  try {
    localStorage.setItem(STATS_KEY, JSON.stringify(stats));
  } catch {
    // Storage blocked or full: stats are optional.
  }
}

// Count each finished game exactly once, however many times it is rendered.
function recordFinishedGame(game) {
  const finished = game.status === "won" || game.status === "lost";
  if (!finished || recordedGames.has(game.game_id)) return;
  recordedGames.add(game.game_id);
  const stats = loadStats();
  stats.played += 1;
  if (game.status === "won") stats.wins += 1;
  stats.totalQuestions += game.questions_asked;
  saveStats(stats);
}

function statsText() {
  const { played, wins, totalQuestions } = loadStats();
  const average = played > 0 ? (totalQuestions / played).toFixed(1) : "–";
  return `Games played: ${played} · Wins: ${wins} · Average questions: ${average}`;
}

// ---------- Talking to the server ----------

async function request(method, path, body) {
  if (state.loading) return; // never double-submit
  const focused = document.activeElement;
  state.lastRequest = { method, path, body };
  state.loading = true;
  state.error = null;
  render(state);

  try {
    const options = { method, headers: { Accept: "application/json" } };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    const data = await response.json().catch(() => null);
    if (response.ok && data && data.game_id) {
      state.game = data;
      recordFinishedGame(data);
    } else {
      state.error = errorFor(response.ok ? 500 : response.status, data);
    }
  } catch {
    state.error = { message: "Couldn't reach the server.", retry: true, restart: false };
  }

  state.loading = false;
  render(state);
  restoreFocus(focused);
}

function errorFor(status, data) {
  const detail = data && typeof data.detail === "string" ? data.detail : "";
  const fallback = status >= 500 ? "Couldn't reach the server." : "Something went wrong.";
  return {
    message: detail || fallback,
    retry: status >= 500 || status === 409, // 409 may be "Still working on your last answer."
    restart: status === 404,                // the server no longer knows this game
  };
}

function retry() {
  if (!state.lastRequest) return;
  const { method, path, body } = state.lastRequest;
  request(method, path, body);
}

function gamePath(action) {
  return `/api/games/${encodeURIComponent(state.game.game_id)}/${action}`;
}

// Start (or Play again): forget everything about the previous game.
function newGame() {
  state.game = null;
  state.error = null;
  state.lastRequest = null;
  $("reveal-input").value = "";
  request("POST", "/api/games");
}

// ---------- Rendering ----------

function screenFor(game) {
  if (!game) return "start";
  if (game.status === "question") return "play";
  if (game.status === "guess") return "guess";
  return "result"; // "won" or "lost"
}

// Guesses read better without trailing punctuation: "Is it a giraffe?" not "Is it a giraffe.?"
function cleanGuess(text) {
  return (text || "").trim().replace(/[.?!]+$/, "");
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function fillList(list, items) {
  list.replaceChildren(...items.map((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    return item;
  }));
}

function setProgress(bar, game) {
  const percent = Math.min(100, (game.questions_asked / game.max_questions) * 100);
  bar.style.width = `${percent}%`;
}

// Screen readers hear the new question, guess or result once (only when it changes).
function announce(text) {
  const announcer = $("announcer");
  if (announcer.textContent !== text) announcer.textContent = text;
}

function render(state) {
  const game = state.game;
  const screen = screenFor(game);
  let announcement = "";

  $("start-screen").hidden = screen !== "start";
  $("play-screen").hidden = screen !== "play";
  $("guess-screen").hidden = screen !== "guess";
  $("result-screen").hidden = screen !== "result";

  if (screen === "start") {
    $("stats").textContent = statsText();
  }

  if (screen === "play") {
    const number = Math.min(game.questions_asked + 1, game.max_questions);
    const rejected = game.rejected_guesses;
    $("question-counter").textContent = `Question ${number} of ${game.max_questions}`;
    $("play-guess-info").textContent = rejected.length
      ? `Guess ${rejected.length + 1} of ${game.max_guesses} next`
      : "";
    $("ruled-out").hidden = rejected.length === 0;
    fillList($("ruled-out-list"), rejected.map(cleanGuess));
    setProgress($("play-progress"), game);
    $("question-text").textContent = game.question || "";
    announcement = `Question ${number}. ${game.question || ""}`;
  }

  if (screen === "guess") {
    const guess = cleanGuess(game.guess);
    $("guess-counter").textContent = `Guess ${game.guesses_made} of ${game.max_guesses}`;
    $("guess-questions").textContent = `After ${plural(game.questions_asked, "question")}`;
    setProgress($("guess-progress"), game);
    $("guess-text").textContent = guess;
    announcement = `Is it ${guess}?`;
  }

  if (screen === "result") {
    const won = game.status === "won";
    const rejected = game.rejected_guesses;
    $("result-screen").dataset.outcome = game.status;
    $("result-title").textContent = won ? "I got it!" : "You beat me!";
    $("result-text").textContent = won ? `It was ${cleanGuess(game.guess)}.` : "I ran out of guesses.";
    $("result-questions").textContent = `Questions used: ${game.questions_asked} of ${game.max_questions}`;
    $("result-rejected").hidden = rejected.length === 0;
    fillList($("result-rejected-list"), rejected.map(cleanGuess));
    $("reveal-form").hidden = won || Boolean(game.revealed_answer);
    $("revealed").hidden = !game.revealed_answer;
    $("revealed-answer").textContent = game.revealed_answer || "";
    announcement = `${$("result-title").textContent} ${$("result-text").textContent}`;
    if (game.revealed_answer) announcement += ` You were thinking of: ${game.revealed_answer}`;
  }

  // Loading and error messages
  $("app").classList.toggle("is-loading", state.loading);
  $("loading").hidden = !state.loading;
  $("error").hidden = !state.error;
  if (state.error) {
    $("error-message").textContent = state.error.message;
    $("retry-button").hidden = !state.error.retry;
    $("restart-button").hidden = !state.error.restart;
  }

  // Disable every action while a request is in flight; Undo only when the server allows it.
  for (const button of $("app").querySelectorAll("button")) button.disabled = state.loading;
  $("reveal-input").disabled = state.loading;
  const canUndo = Boolean(game && game.can_undo) && !state.loading;
  $("play-undo").disabled = !canUndo;
  $("guess-undo").disabled = !canUndo;

  announce(announcement);
}

// After a request the clicked button may have been disabled or hidden, which drops
// keyboard focus to the page. Put it back on the same button or the screen's main control.
function restoreFocus(previous) {
  if (!keyboardUser) return;
  const usable = (el) => el && el !== document.body && !el.disabled && el.getClientRects().length > 0;
  if (usable(document.activeElement)) return;
  const screen = screenFor(state.game);
  const defaults = {
    start: $("start-button"),
    play: document.querySelector(".answer"),
    guess: $("correct-button"),
    result: $("reveal-form").hidden ? $("play-again-button") : $("reveal-input"),
  };
  const errorTarget = state.error && !$("retry-button").hidden ? $("retry-button") : null;
  const target = [errorTarget, previous, defaults[screen]].find(usable);
  if (target) target.focus();
}

// ---------- Event wiring ----------

$("start-button").addEventListener("click", newGame);
$("play-again-button").addEventListener("click", newGame);
$("restart-button").addEventListener("click", newGame);
$("retry-button").addEventListener("click", retry);

document.querySelector(".answers").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-answer]");
  if (button) request("POST", gamePath("answer"), { answer: button.dataset.answer });
});

$("correct-button").addEventListener("click", () => request("POST", gamePath("guess"), { correct: true }));
$("wrong-button").addEventListener("click", () => request("POST", gamePath("guess"), { correct: false }));
$("play-undo").addEventListener("click", () => request("POST", gamePath("undo")));
$("guess-undo").addEventListener("click", () => request("POST", gamePath("undo")));

$("reveal-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const answer = $("reveal-input").value.trim();
  if (!answer) {
    state.error = { message: "Type what you were thinking of first.", retry: false, restart: false };
    render(state);
    return;
  }
  request("POST", gamePath("reveal"), { answer: answer.slice(0, 200) });
});

document.addEventListener("keydown", () => { keyboardUser = true; });
document.addEventListener("pointerdown", () => { keyboardUser = false; });

render(state);
