"""Dosya izleyici - degisiklikte otomatik yeniden indexleme.

Docker'a bagli volume'larda (ozellikle Windows/NFS) native dosya olaylari
guvenilir calismadigi icin PollingObserver kullaniyoruz.
Degisiklikler kuyruklanir ve debounce ile toplu islenir.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from . import chunker
from .indexer import indexer

logger = logging.getLogger("anka.rag.watcher")

_DEBOUNCE_SECONDS = 3.0
_POLL_INTERVAL = 15  # saniye


class _Handler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
        self._loop = loop
        self._queue = queue

    def _enqueue(self, event_type: str, src_path: str) -> None:
        path = Path(src_path)
        if any(chunker.should_skip_dir(part) for part in path.parts):
            return
        if event_type != "deleted" and not chunker.is_indexable(path):
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (event_type, path))

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._enqueue("changed", str(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._enqueue("changed", str(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._enqueue("deleted", str(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._enqueue("deleted", str(event.src_path))
            self._enqueue("changed", str(event.dest_path))


class RagWatcher:
    def __init__(self) -> None:
        self._observer: PollingObserver | None = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._observer = PollingObserver(timeout=_POLL_INTERVAL)
        self._observer.schedule(
            _Handler(loop, self._queue), str(indexer.root), recursive=True
        )
        self._observer.daemon = True
        self._observer.start()
        self._task = asyncio.create_task(self._process_loop())
        logger.info("RAG watcher basladi: %s", indexer.root)

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
        if self._task:
            self._task.cancel()

    async def _process_loop(self) -> None:
        while True:
            first = await self._queue.get()
            pending: dict[Path, str] = {first[1]: first[0]}
            # Debounce: kisa sure icinde gelen diger degisiklikleri topla
            try:
                while True:
                    event_type, path = await asyncio.wait_for(
                        self._queue.get(), timeout=_DEBOUNCE_SECONDS
                    )
                    pending[path] = event_type
            except asyncio.TimeoutError:
                pass

            for path, event_type in pending.items():
                try:
                    if event_type == "deleted":
                        rel = path.relative_to(indexer.root.resolve()).as_posix()
                        await indexer.remove_file(rel)
                        logger.info("Index'ten silindi: %s", rel)
                    else:
                        written = await indexer.index_file(path)
                        if written:
                            logger.info(
                                "Yeniden indexlendi: %s (%d chunk)", path, written
                            )
                except Exception as exc:
                    logger.warning("Watcher isleme hatasi (%s): %s", path, exc)


watcher = RagWatcher()
