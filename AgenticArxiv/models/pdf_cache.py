# AgenticArxiv/models/pdf_cache.py
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Optional, Literal

from pydantic import BaseModel, Field


PdfAssetStatus = Literal["NOT_DOWNLOADED", "DOWNLOADING", "READY", "FAILED"]


class PdfAsset(BaseModel):
    paper_id: str
    pdf_url: str
    local_path: str
    status: PdfAssetStatus = "NOT_DOWNLOADED"
    size_bytes: int = 0
    sha256: Optional[str] = None
    downloaded_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None


class PdfCacheIndex:
    """
    持久化 PDF 缓存索引：json 文件
    结构示例：
    {
      "version": 1,
      "updated_at": "...",
      "assets": {
        "2602.09017v1": { ... PdfAsset ... }
      }
    }
    """

    def __init__(self, path: str):
        self.path = path
        self.assets: Dict[str, PdfAsset] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            self.assets = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_assets = data.get("assets", {}) if isinstance(data, dict) else {}
            assets: Dict[str, PdfAsset] = {}
            for k, v in raw_assets.items():
                if isinstance(v, dict):
                    assets[k] = PdfAsset(**v)
            self.assets = assets
        except Exception:
            # 读失败就当空索引，避免影响主流程
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

    def get(self, paper_id: str) -> Optional[PdfAsset]:
        return self.assets.get(paper_id)

    def upsert(self, asset: PdfAsset, save: bool = True) -> PdfAsset:
        asset.updated_at = datetime.now()
        self.assets[asset.paper_id] = asset
        if save:
            self.save()
        return asset

    def update(self, paper_id: str, save: bool = True, **kwargs) -> Optional[PdfAsset]:
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

    def delete(self, paper_id: str, save: bool = True) -> bool:
        """
        从索引中删除一条记录（不负责删文件，只维护 json）。
        """
        if paper_id not in self.assets:
            return False
        self.assets.pop(paper_id, None)
        if save:
            self.save()
        return True
