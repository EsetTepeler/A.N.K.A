"""Tool kayit merkezi.

Her arac bir risk sinifina sahiptir:
  SAFE        -> otomatik calisir
  WRITE       -> onay gerekir (Faz 3'te onay mekanizmasi devreye girecek)
  DESTRUCTIVE -> acik onay + audit log gerekir
FORBIDDEN islemler hic kaydedilmez, LLM bu araclari asla goremez.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    WRITE = "WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema (Gemini function declaration uyumlu)
    handler: Callable[..., Awaitable[Any]]
    risk: RiskLevel = RiskLevel.SAFE


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict | None = None,
        risk: RiskLevel = RiskLevel.SAFE,
    ):
        def decorator(fn: Callable[..., Awaitable[Any]]):
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                parameters=parameters or {"type": "object", "properties": {}},
                handler=fn,
                risk=risk,
            )
            return fn

        return decorator

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def gemini_declarations(self) -> list[dict]:
        """Gemini function_declarations formatinda tum araclar."""
        return [
            {
                "name": t.name,
                "description": f"[risk: {t.risk.value}] {t.description}",
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, args: dict) -> Any:
        spec = self.get(name)
        if spec is None:
            return {"error": f"Bilinmeyen arac: {name}"}
        # Faz 3: WRITE/DESTRUCTIVE icin onay mekanizmasi buraya girecek.
        # Simdilik yalnizca SAFE araclar kayitli oldugu icin dogrudan calistiriyoruz.
        try:
            result = spec.handler(**args)
            if inspect.isawaitable(result):
                result = await result
            return result
        except Exception as exc:  # arac hatasi LLM'e geri doner, sistem cokmez
            return {"error": f"{type(exc).__name__}: {exc}"}


registry = ToolRegistry()
