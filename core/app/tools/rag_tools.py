"""RAG araclari - ajanin kod tabaninda arama yapmasini saglar."""
from __future__ import annotations

from ..rag.indexer import indexer
from .registry import registry


@registry.register(
    name="search_codebase",
    description=(
        "Kullanicinin kod projelerinde semantik arama yapar. "
        "Kod, fonksiyon, mimari veya dokumantasyon sorularinda kullan. "
        "Sorguyu dogal dilde yaz (orn: 'kimlik dogrulama akisi', 'veritabani baglantisi')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Dogal dilde arama sorgusu",
            },
            "project": {
                "type": "string",
                "description": "Istege bagli: aramayi tek projeyle sinirla (proje klasor adi)",
            },
        },
        "required": ["query"],
    },
)
async def search_codebase(query: str, project: str | None = None) -> dict:
    if not indexer.available:
        return {"error": "RAG aktif degil (proje dizini veya API anahtari eksik)."}
    results = await indexer.search(query, project=project)
    if not results:
        return {"info": "Sonuc bulunamadi. Index bos olabilir; once indexleme gerekebilir."}
    return {"results": results}


@registry.register(
    name="list_projects",
    description="Indexlenebilir kod projelerinin listesini dondurur.",
)
async def list_projects() -> dict:
    projects = await indexer.list_projects()
    return {"projects": projects, "index_status": indexer.status}
