"""Language model gateway.

Production path: vLLM serving the fine-tuned Mistral-7B (OpenAI-compatible
API) — see finetune/ and docs/09-fine-tuning.md. LiteLLM provides the routing
shim for the frontier fallback (gpt-4o-mini) when the fine-tuned model's
confidence is too low.

Every completion reports token usage and estimated cost so the orchestrator
can write a UsageRecord row per agent step.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field

from app.config import get_settings

# Approximate USD per 1M tokens. Self-hosted vLLM prices model the amortized
# GPU+electricity cost; cloud values are list prices. Used for cost accounting
# only — docs/16-cost-optimization.md has the full model.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "conductor/mistral-7b": {"input": 0.02, "output": 0.06},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}

MAX_OUTPUT_TOKENS = 1024


@dataclass
class Completion:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    finish_reason: str = ""
    tool_calls: list[dict[str, object]] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (input_tokens / 1_000_000 * price["input"]) + (output_tokens / 1_000_000 * price["output"])


class LLMUnavailableError(RuntimeError):
    pass


def complete(
    messages: Sequence[dict[str, str]],
    *,
    tools: list[dict[str, object]] | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    json_mode: bool = False,
    max_tokens: int = MAX_OUTPUT_TOKENS,
    agent: str = "unknown",
) -> Completion:
    """Synchronous completion against vLLM (used by Celery-heavy paths)."""
    import httpx
    from openai import OpenAI

    settings = get_settings()
    model = model or settings.model_id
    client = OpenAI(base_url=settings.vllm_base_url, api_key=settings.vllm_api_key, timeout=httpx.Timeout(120.0))

    try:
        response = client.chat.completions.create(
            model=model,
            messages=list(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            response_format={"type": "json_object"} if json_mode else None,
        )
    except Exception as exc:  # OpenAIError, APIConnectionError, etc.
        raise LLMUnavailableError(f"{agent}: model call failed ({exc})") from exc

    choice = response.choices[0]
    message = choice.message
    usage = response.usage
    return Completion(
        content=message.content or "",
        model=model,
        input_tokens=getattr(usage, "prompt_tokens", 0),
        output_tokens=getattr(usage, "completion_tokens", 0),
        cost_usd=_estimate_cost(model, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0)),
        finish_reason=choice.finish_reason or "",
        tool_calls=(
            [
                {"name": tc.function.name, "arguments": tc.function.arguments}
                for tc in (message.tool_calls or [])
            ]
            if message.tool_calls
            else []
        ),
    )


async def stream_complete(
    messages: Sequence[dict[str, str]],
    *,
    tools: list[dict[str, object]] | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    agent: str = "unknown",
) -> AsyncIterator[tuple[str, Completion | None]]:
    """Stream tokens as (delta, None) and finish with (None, Completion)."""
    import httpx
    from openai import AsyncOpenAI

    settings = get_settings()
    model = model or settings.model_id
    client = AsyncOpenAI(base_url=settings.vllm_base_url, api_key=settings.vllm_api_key, timeout=httpx.Timeout(120.0))

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=list(messages),
            temperature=temperature,
            max_tokens=MAX_OUTPUT_TOKENS,
            tools=tools,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            delta = choice.delta if choice else None
            if delta and delta.content:
                yield delta.content, None
            if chunk.usage:
                yield None, Completion(
                    content="",
                    model=model,
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                    cost_usd=_estimate_cost(model, chunk.usage.prompt_tokens, chunk.usage.completion_tokens),
                )
    except Exception as exc:
        raise LLMUnavailableError(f"{agent}: model call failed ({exc})") from exc


def chat_with_fallback(messages: Sequence[dict[str, str]], *, agent: str = "unknown") -> Completion:
    """Try fine-tuned model; escalate to frontier model on failure or low budget."""
    try:
        return complete(messages, agent=agent)
    except LLMUnavailableError:
        settings = get_settings()
        return complete(messages, model=settings.fallback_model_id, agent=agent)