"""RAG indexleyici.

- Proje kok dizinini tarar, degisen dosyalari (hash karsilastirmali) indexler
- Chunk'lari Gemini ile embed edip Qdrant'a yazar
- Arama: dense vektor benzerligi (cosine)

Manifest (dosya -> hash) SQLite'ta tutulur; boylece yeniden baslatmada
yalnizca degisen dosyalar islenir.
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path

import aiosqlite
from qdrant_client import AsyncQdrantClient, models

from ..config import settings
from . import chunker, embedder

_MANIFEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS indexed_files (
    path TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    chunks INTEGER NOT NULL DEFAULT 0,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _point_id(rel_path: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"anka:{rel_path}:{chunk_index}"))


class Indexer:
    def __init__(self) -> None:
        self._client: AsyncQdrantClient | None = None
        self.root = Path(settings.anka_projects_root)
        self.status: dict = {"state": "idle", "files": 0, "chunks": 0, "errors": 0}
        self._lock = asyncio.Lock()

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(url=settings.qdrant_url)
        return self._client

    @property
    def available(self) -> bool:
        return bool(settings.gemini_api_key) and self.root.exists()

    # --- kurulum ---

    async def ensure_ready(self) -> None:
        async with aiosqlite.connect(settings.anka_db_path) as db:
            await db.executescript(_MANIFEST_SCHEMA)
            await db.commit()

        if not await self.client.collection_exists(settings.qdrant_collection):
            await self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=models.VectorParams(
                    size=settings.embedding_dim,
                    distance=models.Distance.COSINE,
                ),
            )
            for field in ("path", "project"):
                await self.client.create_payload_index(
                    collection_name=settings.qdrant_collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )

    # --- manifest ---

    async def _manifest_get(self, rel_path: str) -> str | None:
        async with aiosqlite.connect(settings.anka_db_path) as db:
            cur = await db.execute(
                "SELECT hash FROM indexed_files WHERE path = ?", (rel_path,)
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def _manifest_set(self, rel_path: str, file_hash: str, chunks: int) -> None:
        async with aiosqlite.connect(settings.anka_db_path) as db:
            await db.execute(
                "INSERT INTO indexed_files (path, hash, chunks) VALUES (?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET hash=excluded.hash, "
                "chunks=excluded.chunks, indexed_at=CURRENT_TIMESTAMP",
                (rel_path, file_hash, chunks),
            )
            await db.commit()

    async def _manifest_delete(self, rel_path: str) -> None:
        async with aiosqlite.connect(settings.anka_db_path) as db:
            await db.execute("DELETE FROM indexed_files WHERE path = ?", (rel_path,))
            await db.commit()

    # --- indexleme ---

    def _walk(self) -> list[Path]:
        files: list[Path] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or not chunker.is_indexable(path):
                continue
            if any(chunker.should_skip_dir(part) for part in path.parts):
                continue
            files.append(path)
        return files

    def _rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _project_of(self, rel_path: str) -> str:
        return rel_path.split("/", 1)[0] if "/" in rel_path else "(kok)"

    async def index_file(self, path: Path) -> int:
        """Tek dosyayi indexler. Donen deger: yazilan chunk sayisi."""
        rel_path = self._rel(path)
        file_hash = _file_hash(path)
        if await self._manifest_get(rel_path) == file_hash:
            return 0  # degismemis

        chunks = chunker.chunk_file(path)
        # Eski chunk'lari sil (chunk sayisi degismis olabilir)
        await self.client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="path", match=models.MatchValue(value=rel_path)
                        )
                    ]
                )
            ),
        )
        if not chunks:
            await self._manifest_set(rel_path, file_hash, 0)
            return 0

        vectors = await embedder.embed_documents([c.text for c in chunks])
        points = [
            models.PointStruct(
                id=_point_id(rel_path, i),
                vector=vec,
                payload={
                    "path": rel_path,
                    "project": self._project_of(rel_path),
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "text": c.text,
                },
            )
            for i, (c, vec) in enumerate(zip(chunks, vectors))
        ]
        await self.client.upsert(
            collection_name=settings.qdrant_collection, points=points
        )
        await self._manifest_set(rel_path, file_hash, len(points))
        return len(points)

    async def remove_file(self, rel_path: str) -> None:
        await self.client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="path", match=models.MatchValue(value=rel_path)
                        )
                    ]
                )
            ),
        )
        await self._manifest_delete(rel_path)

    async def index_all(self) -> dict:
        """Tum proje dizinini artimli olarak indexler."""
        async with self._lock:
            self.status = {"state": "indexing", "files": 0, "chunks": 0, "errors": 0}
            for path in self._walk():
                try:
                    written = await self.index_file(path)
                    self.status["files"] += 1
                    self.status["chunks"] += written
                except Exception:
                    self.status["errors"] += 1
            self.status["state"] = "ready"
            return dict(self.status)

    # --- arama ---

    async def search(
        self, query: str, project: str | None = None, limit: int = 5
    ) -> list[dict]:
        vector = await embedder.embed_query(query)
        flt = None
        if project:
            flt = models.Filter(
                must=[
                    models.FieldCondition(
                        key="project", match=models.MatchValue(value=project)
                    )
                ]
            )
        hits = await self.client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            query_filter=flt,
            limit=limit,
        )
        results = []
        for hit in hits.points:
            payload = hit.payload or {}
            results.append(
                {
                    "path": payload.get("path"),
                    "lines": f"{payload.get('start_line')}-{payload.get('end_line')}",
                    "score": round(hit.score, 3),
                    "text": (payload.get("text") or "")[:1500],
                }
            )
        return results

    async def list_projects(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(
            p.name
            for p in self.root.iterdir()
            if p.is_dir() and not chunker.should_skip_dir(p.name)
        )


indexer = Indexer()
