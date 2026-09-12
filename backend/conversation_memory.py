from collections import defaultdict

MAX_HISTORY_TURNS = 5

# Per-user conversation history: {user_id: [{"question": ..., "answer": ...}, ...]}
_conversation_history: dict = defaultdict(list)

def add_turn(user_id: int, question: str, answer: str):
    history = _conversation_history[user_id]
    history.append({"question": question, "answer": answer})
    if len(history) > MAX_HISTORY_TURNS:
        _conversation_history[user_id] = history[-MAX_HISTORY_TURNS:]

def get_history(user_id: int) -> list:
    return _conversation_history.get(user_id, [])

def clear_history(user_id: int):
    _conversation_history[user_id] = []

def format_history(user_id: int) -> str:
    """Returns the recent history formatted as plain text for prompt injection."""
    history = get_history(user_id)
    if not history:
        return "(no prior conversation)"
    lines = []
    for turn in history:
        lines.append(f"Q: {turn['question']}\nA: {turn['answer']}")
    return "\n\n".join(lines)