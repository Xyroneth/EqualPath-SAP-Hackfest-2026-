"""LearningCatalogProvider: curated SAP Learning catalog today; replaceable by an authorized connector later."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import load_json


class LearningCatalogProvider(ABC):
    kind = "abstract"

    @abstractmethod
    def all(self) -> list[dict]: ...

    def get(self, asset_id: str) -> dict | None:
        return next((a for a in self.all() if a["asset_id"] == asset_id), None)

    def for_capability(self, capability: str) -> list[dict]:
        """SAP assets first, then external open resources."""
        hits = [a for a in self.all() if capability in a["capability_tags"]]
        return sorted(hits, key=lambda a: (not a["provider"].startswith("SAP"), a["estimated_hours"]))


class CuratedLocalCatalog(LearningCatalogProvider):
    kind = "curated_local"

    def __init__(self):
        self._assets = load_json("learning_assets.json")["assets"]

    def all(self) -> list[dict]:
        return self._assets


_catalog: LearningCatalogProvider | None = None


def get_learning_catalog() -> LearningCatalogProvider:
    global _catalog
    if _catalog is None:
        _catalog = CuratedLocalCatalog()
    return _catalog
