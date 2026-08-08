"""Ajan dongusu: LLM -> tool cagrisi -> sonuc -> LLM ... -> nihai yanit.

Sistemin beyni burasi. Her yeni modul (RAG, OS, WhatsApp) sadece
registry'ye yeni tool ekler; bu dongu degismez.
"""
from __future__ import annotations

from typing import AsyncIterator

from google.genai import types

from ..llm.gateway import gateway
from ..tools.registry import registry

MAX_TOOL_ROUNDS = 10  # sonsuz dongu emniyeti


async def run_agent(
    history: list[types.Content],
    user_message: str,
) -> AsyncIterator[dict]:
    """Kullanici mesajini isler, olaylari (tool cagrisi, nihai yanit) yield eder.

    history: onceki turlarin Gemini Content listesi (mutasyona ugrar,
             cagiran taraf guncel halini saklayabilir).
    """
    history.append(gateway.user_content(user_message))
    declarations = registry.gemini_declarations()

    for _ in range(MAX_TOOL_ROUNDS):
        response, model_content = await gateway.generate(
            contents=history,
            tool_declarations=declarations,
        )
        if model_content is not None:
            history.append(model_content)

        if not response.tool_calls:
            yield {"type": "final", "text": response.text or ""}
            return

        # Araclari calistir, sonuclari topla
        results: list[tuple[str, object]] = []
        for call in response.tool_calls:
            yield {"type": "tool_call", "name": call.name, "args": call.args}
            result = await registry.execute(call.name, call.args)
            yield {"type": "tool_result", "name": call.name, "result": result}
            results.append((call.name, result))

        history.append(gateway.tool_result_content(results))

    yield {
        "type": "final",
        "text": "Arac cagrisi limitine ulasildi, islemi tamamlayamadim.",
    }
