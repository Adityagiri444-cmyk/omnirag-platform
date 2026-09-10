import time
from langchain_core.callbacks import BaseCallbackHandler

class TokenUsageTracker(BaseCallbackHandler):
    """Accumulates real token usage across every LLM call made during one graph run."""

    # Shared across all instances - tracks every LLM call's timestamp,
    # used to estimate how close we are to Groq's free-tier rate limit (30 req/min)
    call_timestamps = []

    def __init__(self):
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def on_llm_end(self, response, **kwargs):
        self.llm_calls += 1
        TokenUsageTracker.call_timestamps.append(time.time())
        try:
            usage = response.llm_output.get("token_usage", {})
            self.prompt_tokens += usage.get("prompt_tokens", 0)
            self.completion_tokens += usage.get("completion_tokens", 0)
            self.total_tokens += usage.get("total_tokens", 0)
        except Exception:
            pass

    def summary(self) -> dict:
        return {
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    @staticmethod
    def requests_in_last_minute() -> int:
        cutoff = time.time() - 60
        TokenUsageTracker.call_timestamps = [
            t for t in TokenUsageTracker.call_timestamps if t > cutoff
        ]
        return len(TokenUsageTracker.call_timestamps)