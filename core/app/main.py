"""A.N.K.A Core API - FastAPI giris noktasi."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# Araclarin registry'ye kaydolmasi icin import edilmesi yeterli
from .tools import rag_tools, system_tools  # noqa: F401
from .agent.orchestrator import run_agent
from .memory.conversations import store
from .rag.indexer import indexer
from .rag.watcher import watcher
from .tools.registry import registry

logger = logging.getLogger("anka")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.init()
    if indexer.available:
        try:
            await indexer.ensure_ready()
            asyncio.create_task(indexer.index_all())  # ilk tarama arka planda
            watcher.start()
        except Exception as exc:
            logger.warning("RAG baslatilamadi (sistem RAG'siz devam ediyor): %s", exc)
    else:
        logger.info(
            "RAG devre disi: proje dizini (%s) veya GEMINI_API_KEY eksik.",
            indexer.root,
        )
    yield
    watcher.stop()


app = FastAPI(title="A.N.K.A Core", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "tools": [t.name for t in registry.all()]}


class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str


@app.post("/chat")
async def chat(req: ChatRequest):
    """Basit istek/yanit endpoint'i (test ve entegrasyonlar icin)."""
    history = store.get_history(req.session_id)
    await store.log(req.session_id, "user", req.message)

    events: list[dict] = []
    final_text = ""
    async for event in run_agent(history, req.message):
        events.append(event)
        if event["type"] == "final":
            final_text = event["text"]

    await store.log(req.session_id, "assistant", final_text)
    return {"reply": final_text, "events": events}


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    """Gercek zamanli kanal - ses ve WhatsApp modulleri buraya baglanacak.

    Istemci gonderir: {"session_id": "...", "message": "..."}
    Sunucu yayinlar:  {"type": "tool_call"|"tool_result"|"final", ...}
    """
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            session_id = data.get("session_id", "default")
            message = data.get("message", "")
            if not message:
                await ws.send_json({"type": "error", "detail": "Bos mesaj"})
                continue

            history = store.get_history(session_id)
            await store.log(session_id, "user", message)

            final_text = ""
            async for event in run_agent(history, message):
                await ws.send_json(event)
                if event["type"] == "final":
                    final_text = event["text"]

            await store.log(session_id, "assistant", final_text)
    except WebSocketDisconnect:
        pass


@app.post("/session/{session_id}/reset")
async def reset_session(session_id: str):
    store.reset(session_id)
    return {"status": "reset", "session_id": session_id}


@app.get("/rag/status")
async def rag_status():
    return {
        "available": indexer.available,
        "projects_root": str(indexer.root),
        "status": indexer.status,
        "projects": await indexer.list_projects() if indexer.root.exists() else [],
    }


@app.post("/rag/reindex")
async def rag_reindex():
    if not indexer.available:
        return {"error": "RAG aktif degil (proje dizini veya API anahtari eksik)."}
    try:
        await indexer.ensure_ready()
    except Exception as exc:
        logger.exception("RAG hazirlik hatasi")
        return {"error": f"RAG hazirlik hatasi: {type(exc).__name__}: {exc}"}
    asyncio.create_task(indexer.index_all())
    return {"status": "indexleme baslatildi", "root": str(indexer.root)}
