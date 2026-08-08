"""Gemini embedding katmani.

gemini-embedding-001, output_dimensionality=768 ile kullanilir.
768 boyutta vektorler normalize edilmeden gelir; cosine benzerligi
icin manuel normalize ediyoruz.
"""
from __future__ import annotations

import asyncio
import math

from google.genai import types

from ..config import settings
from ..llm.gateway import gateway

_BATCH_SIZE = 50


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


async def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    results: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        response = await gateway.client.aio.models.embed_content(
            model=settings.embedding_model,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=settings.embedding_dim,
            ),
        )
        results.extend(_normalize(e.values) for e in response.embeddings)
        if i + _BATCH_SIZE < len(texts):
            await asyncio.sleep(0.3)  # ucretsiz kota nefes payi
    return results


async def embed_documents(texts: list[str]) -> list[list[float]]:
    return await _embed(texts, "RETRIEVAL_DOCUMENT")


async def embed_query(text: str) -> list[float]:
    result = await _embed([text], "RETRIEVAL_QUERY")
    return result[0]
