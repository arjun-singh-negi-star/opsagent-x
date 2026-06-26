"""
Thin wrapper around DeepSeek-V4 Flash, served through NVIDIA NIM's
OpenAI-compatible endpoint (https://integrate.api.nvidia.com/v1).

DeepSeek-V4 exposes reasoning depth through `chat_template_kwargs`, not a
different model name. This maps 1:1 to the three modes in the project's
agent pipeline:

    Non-think   -> no kwargs at all (fastest, used for Supervisor routing
                   and the SecurityAgent's quick triage)
    Think High  -> {"thinking": True, "reasoning_effort": "high"}   (LogAnalyst)
    Think Max   -> {"thinking": True, "reasoning_effort": "max"}    (CodeFixer)

Also provides `run_tool_agent`, a small ReAct-style loop shared by every
agent that needs to call tools (K8s logs, PromQL, Trivy, Git) before giving
a final answer.
"""

import json
import logging
from typing import Callable, Literal

from openai import OpenAI

from app.config import settings

logger = logging.getLogger("opsagent.llm")

ReasoningMode = Literal["non_think", "think_high", "think_max"]

_REASONING_KWARGS: dict[ReasoningMode, dict | None] = {
    "non_think": None,
    "think_high": {"thinking": True, "reasoning_effort": "high"},
    "think_max": {"thinking": True, "reasoning_effort": "max"},
}

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        # NVIDIA NIM's free tier caps out around 40 requests/minute, and a
        # single incident can easily use 10+ calls across all agents.
        # The SDK already retries on 429s with backoff (honoring
        # Retry-After when NVIDIA sends one) — we just give it more
        # attempts than the default of 2, since a free-tier rate-limit
        # window can take longer than that to clear.
        _client = OpenAI(base_url=settings.NVIDIA_BASE_URL, api_key=settings.NVIDIA_API_KEY, max_retries=5)
    return _client


def _extra_body(mode: ReasoningMode) -> dict:
    kwargs = _REASONING_KWARGS[mode]
    return {"chat_template_kwargs": kwargs} if kwargs else {}


def estimate_cost_usd(usage: dict, mode: ReasoningMode) -> float:
    """Rough cost estimate for the dashboard's token-cost panel."""
    rate = settings.TOKEN_COST_PER_1K.get(mode, settings.TOKEN_COST_PER_1K["non_think"])
    total_tokens = (usage or {}).get("total_tokens", 0)
    return round((total_tokens / 1000) * rate, 6)


def chat_completion(
    messages: list[dict],
    mode: ReasoningMode = "non_think",
    tools: list[dict] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
):
    """Single call to DeepSeek-V4 Flash. Returns (message, usage_dict, reasoning_text)."""
    client = get_client()
    response = client.chat.completions.create(
        model=settings.DEEPSEEK_MODEL,
        messages=messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body=_extra_body(mode),
    )
    choice = response.choices[0]
    usage = response.usage.model_dump() if response.usage else {}
    reasoning = getattr(choice.message, "reasoning_content", None)
    return choice.message, usage, reasoning


def run_tool_agent(
    system_prompt: str,
    user_prompt: str,
    tools_schema: list[dict],
    tool_executor: Callable[[str, dict], str],
    mode: ReasoningMode,
    max_turns: int = 4,
) -> tuple[str, dict, str | None]:
    """
    Generic tool-calling loop: the model can call any tool in `tools_schema`
    (resolved via `tool_executor`) for up to `max_turns` rounds before it
    must produce a final text answer. Returns (final_text, total_usage, last_reasoning).
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    last_reasoning = None

    for _ in range(max_turns):
        message, usage, reasoning = chat_completion(messages, mode=mode, tools=tools_schema)
        last_reasoning = reasoning or last_reasoning
        for key in total_usage:
            total_usage[key] += usage.get(key, 0)

        if not message.tool_calls:
            return message.content or "", total_usage, last_reasoning

        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            logger.info("tool_call name=%s args=%s", call.function.name, args)
            try:
                result = tool_executor(call.function.name, args)
            except Exception as exc:  # noqa: BLE001
                # A tool raising should never take down the whole incident —
                # hand the model an error string and let it adapt (retry a
                # different approach, or proceed with reduced information).
                logger.exception("Tool '%s' raised an unhandled exception", call.function.name)
                result = f"ERROR: tool '{call.function.name}' failed unexpectedly: {exc}"
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    return "Reached max tool-call turns without a final answer.", total_usage, last_reasoning
