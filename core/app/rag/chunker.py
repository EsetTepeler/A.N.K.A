"""Kod/dokuman parcalayici (chunker).

Dosyalari satir bazli, fonksiyon/sinif sinirlarina saygili parcalara boler.
Basit ve dil-bagimsiz bir sezgisel yaklasim; ileride tree-sitter ile
tam sozdizimi-farkindali bolmeye yukseltilebilir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Indexlenecek uzantilar
INDEXABLE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".kt", ".swift",
    ".md", ".txt", ".rst",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".env.example",
    ".html", ".css", ".scss", ".sql", ".sh", ".ps1", ".bat", ".dockerfile",
}

# Atlanacak dizinler
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", "target", ".next", ".idea", ".vscode",
    "bin", "obj", "coverage", ".tox", "vendor",
}

MAX_FILE_BYTES = 300_000  # cok buyuk dosyalari atla (muhtemelen uretilmis)

# Fonksiyon/sinif baslangici gibi gorunen satirlar - tercih edilen bolme noktalari
_BOUNDARY_RE = re.compile(
    r"^(def |class |async def |function |export |const |public |private |"
    r"protected |static |fn |func |impl |interface |type |struct |#{1,3} )"
)


@dataclass
class Chunk:
    text: str
    start_line: int  # 1-bazli
    end_line: int


def is_indexable(path: Path) -> bool:
    if path.name.lower() == "dockerfile":
        return True
    return path.suffix.lower() in INDEXABLE_EXTS


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")


def chunk_file(path: Path, max_lines: int = 80, hard_limit: int = 140) -> list[Chunk]:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    lines = text.splitlines()
    if not lines:
        return []

    chunks: list[Chunk] = []
    start = 0
    i = 0
    while i < len(lines):
        size = i - start
        line = lines[i]
        at_boundary = _BOUNDARY_RE.match(line) or line.strip() == ""
        if (size >= max_lines and at_boundary) or size >= hard_limit:
            chunk_text = "\n".join(lines[start:i]).strip()
            if chunk_text:
                chunks.append(Chunk(chunk_text, start + 1, i))
            start = i
        i += 1

    tail = "\n".join(lines[start:]).strip()
    if tail:
        chunks.append(Chunk(tail, start + 1, len(lines)))

    return chunks
