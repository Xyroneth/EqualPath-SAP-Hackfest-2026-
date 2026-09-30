"""Seed data loaders: the fictional persona and her real evidence files."""
from __future__ import annotations

from app.config import DATA_DIR, load_json
from app.documents import EXT_INFO, ext_of, extract_text

EVIDENCE_DIR = DATA_DIR / "evidence"


def load_persona() -> dict:
    return load_json("persona_priya.json")


def seed_files() -> list[tuple[dict, bytes]]:
    """Priya's evidence as (document record incl. extracted text, file bytes). Text comes from the real files."""
    out = []
    for meta in load_persona()["documents"]:
        data = (EVIDENCE_DIR / meta["file"]).read_bytes()
        text, kind = extract_text(meta["file"], data)
        mime = EXT_INFO[ext_of(meta["file"])][0]
        out.append(({"source_id": meta["source_id"], "title": meta["title"], "evidence_type": meta["evidence_type"], "date": meta["date"],
                     "filename": meta["file"], "mime": mime, "size": len(data), "kind": kind, "seed": True, "text": text}, data))
    return out


def seed_documents() -> list[dict]:
    return [d for d, _ in seed_files()]
