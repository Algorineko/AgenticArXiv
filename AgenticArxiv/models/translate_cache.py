# AgenticArxiv/models/translate_cache.py
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Optional, Literal

from pydantic import BaseModel, Field

TranslateAssetStatus = Literal["NOT_TRANSLATED", "TRANSLATING", "READY", "FAILED"]


class TranslateAsset(BaseModel):
    paper_id: str
    input_pdf_path: str
    output_mono_path: str
    output_dual_path: Optional[str] = None

    status: TranslateAssetStatus = "NOT_TRANSLATED"
    service: Optional[str] = None
    threads: int = 0

    translated_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None


class TranslateCacheIndex:
    """
    translate_cache.json:
    {
      "version": 1,
      "updated_at": "...",
      "assets": {
        "2602.09017v1": {... TranslateAsset ...}
      }
    }
    """

    def __init__(self, path: str):
        self.path = path
        self.assets: Dict[str, TranslateAsset] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            self.assets = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_assets = data.get("assets", {}) if isinstance(data, dict) else {}
            assets: Dict[str, TranslateAsset] = {}
            for k, v in raw_assets.items():
                if isinstance(v, dict):
                    assets[k] = TranslateAsset(**v)
            self.assets = assets
        except Exception:
            self.assets = {}

    def _atomic_write_json(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)

    def save(self) -> None:
        payload = {
            "version": 1,
            "updated_at": datetime.now().isoformat(),
            "assets": {k: json.loads(v.json()) for k, v in self.assets.items()},
        }
        self._atomic_write_json(payload)

    def get(self, paper_id: str) -> Optional[TranslateAsset]:
        return self.assets.get(paper_id)

    def upsert(self, asset: TranslateAsset, save: bool = True) -> TranslateAsset:
        asset.updated_at = datetime.now()
        self.assets[asset.paper_id] = asset
        if save:
            self.save()
        return asset

    def update(self, paper_id: str, save: bool = True, **kwargs) -> Optional[TranslateAsset]:
        a = self.assets.get(paper_id)
        if not a:
            return None
        for k, v in kwargs.items():
            setattr(a, k, v)
        a.updated_at = datetime.now()
        self.assets[paper_id] = a
        if save:
            self.save()
        return a
