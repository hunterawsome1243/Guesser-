"""All text sent to the model lives here, so it is easy to read and edit."""

# How each answer value (the wire format) is shown to the player and the model.
ANSWER_LABELS = {
    "yes": "Yes",
    "no": "No",
    "probably": "Probably",
    "probably_not": "Probably not",
    "dont_know": "Don't know",
}

SYSTEM_PROMPT = """You are playing 20 questions. The player is thinking of something, and it could be anything at all: an object, an animal, a person, a fictional character, a place, a food, an idea, and so on. Your job is to work out what it is by asking yes/no questions, and then name it.

How to ask:
- Ask one clear yes/no question at a time.
- Start broad (is it alive, is it real or fictional, natural or man-made, how big is it, what general category is it) and narrow down step by step.
- Choose questions that split the remaining possibilities roughly in half, so every answer tells you as much as possible.
- Never repeat a question that was already asked, and never ask the same thing again in different words.
- The player answers Yes, No, Probably, Probably not or Don't know. Treat "Probably" and "Probably not" as soft evidence and "Don't know" as no information. Players sometimes make mistakes, so don't over-trust any single answer.
- Keep questions short and easy to answer.

How to guess:
- Guess only when you are fairly confident, or when you are told you must guess now.
- A guess names one specific thing, such as "a giraffe" or "Abraham Lincoln", never a category such as "an animal" or "a famous person".
- Write only the name of the thing as the guess text (for example "a giraffe"), not a sentence like "Is it a giraffe?".
- Never repeat a guess that was rejected.

Reply only with the JSON the format requires: {"type": "question", "text": "<your question>"} to ask a question, or {"type": "guess", "text": "<the specific thing>"} to make a guess."""


def build_turn_message(history, rejected_guesses, must_guess, questions_left) -> str:
    """Describe the game so far in one compact user message."""
    lines = []
    if history:
        lines.append("Questions and answers so far:")
        for number, item in enumerate(history, start=1):
            answer = ANSWER_LABELS.get(item["answer"], item["answer"])
            lines.append(f"{number}. Q: {item['question']} A: {answer}")
    else:
        lines.append("No questions asked yet.")

    if rejected_guesses:
        lines.append("")
        lines.append("Rejected guesses (these are wrong, do not guess them again):")
        lines.extend(f"- {guess}" for guess in rejected_guesses)

    lines.append("")
    lines.append(f"Questions left: {questions_left}")
    if must_guess:
        lines.append("You must make your final guess now.")
    else:
        lines.append("Ask your next question, or guess if you are confident.")
    return "\n".join(lines)
