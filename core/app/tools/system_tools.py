"""Faz 1 demo araclari - hepsi SAFE sinifi.

Faz 3'te buraya gercek OS araclari (terminal, dosya yazma vb.)
onay mekanizmasiyla birlikte eklenecek.
"""
from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path

from .registry import RiskLevel, registry


@registry.register(
    name="get_current_time",
    description="Su anki tarih ve saati dondurur.",
)
async def get_current_time() -> dict:
    now = datetime.now()
    return {
        "iso": now.isoformat(timespec="seconds"),
        "human": now.strftime("%d.%m.%Y %H:%M"),
    }


@registry.register(
    name="get_system_info",
    description="Uzerinde calistigi sistemin bilgilerini dondurur (OS, Python surumu vb.)",
)
async def get_system_info() -> dict:
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }


@registry.register(
    name="list_directory",
    description="Verilen dizindeki dosya ve klasorleri listeler (sadece okuma).",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Listelenecek dizinin yolu, orn: C:/Projeler",
            }
        },
        "required": ["path"],
    },
    risk=RiskLevel.SAFE,
)
async def list_directory(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"error": f"Dizin bulunamadi: {path}"}
    if not p.is_dir():
        return {"error": f"Bu bir dizin degil: {path}"}
    entries = []
    for child in sorted(p.iterdir())[:200]:
        entries.append({"name": child.name, "type": "dir" if child.is_dir() else "file"})
    return {"path": str(p), "count": len(entries), "entries": entries}
