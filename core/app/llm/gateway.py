"""LLM Gateway - tum model cagrilari bu katmandan gecer.

Su an tek saglayici: Google Gemini (google-genai SDK).
Ileride lokal model (Ollama) veya baska saglayici eklemek icin
sadece bu dosyaya yeni bir adapter yazilir; sistemin geri kalani degismez.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from ..config import settings


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class GeminiGateway:
    def __init__(self) -> None:
        self._client: genai.Client | None = None
        self._model = settings.gemini_model

    @property
    def client(self) -> genai.Client:
        # Lazy: API anahtari olmadan da uygulama ayaga kalkabilsin
        if self._client is None:
            if not settings.gemini_api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY tanimli degil. .env dosyasini kontrol et."
                )
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    async def generate(
        self,
        contents: list[types.Content],
        tool_declarations: list[dict] | None = None,
        system_prompt: str | None = None,
    ) -> tuple[LLMResponse, types.Content | None]:
        """Tek bir model cagrisi yapar.

        Donen deger: (yanit, modelin urettigi ham Content)
        Ham Content konusma gecmisine eklenmek icin gerekli.
        """
        config = types.GenerateContentConfig(
            system_instruction=system_prompt or settings.system_prompt,
        )
        if tool_declarations:
            config.tools = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(**decl) for decl in tool_declarations
                    ]
                )
            ]

        response = await self.client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0] if response.candidates else None
        model_content = candidate.content if candidate else None

        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []
        if model_content and model_content.parts:
            for part in model_content.parts:
                if part.function_call:
                    tool_calls.append(
                        ToolCall(
                            name=part.function_call.name,
                            args=dict(part.function_call.args or {}),
                        )
                    )
                elif part.text:
                    text_parts.append(part.text)

        return (
            LLMResponse(text="".join(text_parts) or None, tool_calls=tool_calls),
            model_content,
        )

    @staticmethod
    def user_content(text: str) -> types.Content:
        return types.Content(role="user", parts=[types.Part(text=text)])

    @staticmethod
    def tool_result_content(results: list[tuple[str, Any]]) -> types.Content:
        """Arac sonuclarini Gemini'nin bekledigi formata cevirir."""
        parts = [
            types.Part.from_function_response(name=name, response={"result": result})
            for name, result in results
        ]
        return types.Content(role="user", parts=parts)


gateway = GeminiGateway()
