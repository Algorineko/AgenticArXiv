# AgenticArxiv/models/store.py
from __future__ import annotations
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
import re
import uuid
import os
import threading

from models.schemas import Paper, SessionState, TranslateTask
from models.pdf_cache import PdfCacheIndex, PdfAsset
from models.translate_cache import TranslateCacheIndex, TranslateAsset
from config import settings

_REF_RE = re.compile(r"(?:第)?\s*(\d+)\s*(?:篇)?")


class InMemoryStore:
    """
    MVP: 单进程内存存储
    - sessions[session_id].last_papers 作为“短期记忆”
    - sessions[session_id].last_active_paper_id 作为“最近一次操作的论文”（用于 ref=null 指代）
    - tasks[task_id] 存翻译任务状态（内存）
    - pdf_cache.json 持久化 PDF 缓存索引
    - translate_cache.json 持久化翻译缓存索引

    说明：
    - 本实现用于单进程 MVP；多进程/多副本需换成 Redis/DB + PubSub
    """

    def __init__(self, ttl_minutes: int = 60, max_papers: int = 50):
        self.sessions: Dict[str, SessionState] = {}
        self.tasks: Dict[str, TranslateTask] = {}
        self._lock = threading.RLock()

        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_papers = max_papers

        # --- PDF cache index (persistent) ---
        os.makedirs(settings.pdf_raw_path, exist_ok=True)
        os.makedirs(os.path.dirname(settings.pdf_cache_path), exist_ok=True)
        self.pdf_cache = PdfCacheIndex(settings.pdf_cache_path)

        # --- Translate cache index (persistent) ---
        os.makedirs(settings.pdf_translated_path, exist_ok=True)
        os.makedirs(os.path.dirname(settings.translate_cache_path), exist_ok=True)
        self.translate_cache = TranslateCacheIndex(settings.translate_cache_path)

    # -------- session memory --------
    def _get_or_create_session(self, session_id: str) -> SessionState:
        st = self.sessions.get(session_id)
        if st is None:
            st = SessionState(session_id=session_id)
            self.sessions[session_id] = st
        return st

    def _expired(self, t: Optional[datetime]) -> bool:
        if t is None:
            return True
        return (datetime.now() - t) > self.ttl

    def set_last_papers(self, session_id: str, papers: List[Paper]) -> None:
        with self._lock:
            st = self._get_or_create_session(session_id)
            st.last_papers = papers[: self.max_papers]
            st.updated_at = datetime.now()

    def get_last_papers(self, session_id: str) -> List[Paper]:
        with self._lock:
            st = self.sessions.get(session_id)
            if not st:
                return []

            if datetime.now() - st.updated_at > self.ttl:
                st.last_papers = []
            return st.last_papers

    # -------- last active paper --------
    def set_last_active_paper_id(self, session_id: str, paper_id: str) -> None:
        if not paper_id:
            return
        with self._lock:
            st = self._get_or_create_session(session_id)
            st.last_active_paper_id = paper_id
            st.last_active_at = datetime.now()
            st.updated_at = datetime.now()

    def get_last_active_paper_id(self, session_id: str) -> Optional[str]:
        with self._lock:
            st = self.sessions.get(session_id)
            if not st:
                return None

            if st.last_active_at and self._expired(st.last_active_at):
                st.last_active_paper_id = None
                st.last_active_at = None
                return None

            return st.last_active_paper_id

    def resolve_paper(
        self, session_id: str, ref: Union[str, int, None]
    ) -> Optional[Paper]:
        papers = self.get_last_papers(session_id)
        if not papers:
            return None

        if ref is None:
            last_id = self.get_last_active_paper_id(session_id)
            if not last_id:
                return None
            for p in papers:
                if p.id == last_id:
                    return p
            return None

        if isinstance(ref, int):
            idx = ref - 1
            return papers[idx] if 0 <= idx < len(papers) else None

        s = str(ref).strip()

        m = _REF_RE.fullmatch(s)
        if m:
            idx = int(m.group(1)) - 1
            return papers[idx] if 0 <= idx < len(papers) else None

        for p in papers:
            if p.id == s:
                return p

        low = s.lower()
        for p in papers:
            if low in (p.title or "").lower():
                return p

        return None

    # -------- PDF cache (thread-safe wrapper) --------
    def get_pdf_asset(self, paper_id: str) -> Optional[PdfAsset]:
        with self._lock:
            return self.pdf_cache.get(paper_id)

    def upsert_pdf_asset(self, asset: PdfAsset) -> PdfAsset:
        with self._lock:
            return self.pdf_cache.upsert(asset, save=True)

    def update_pdf_asset(self, paper_id: str, **kwargs) -> Optional[PdfAsset]:
        with self._lock:
            return self.pdf_cache.update(paper_id, save=True, **kwargs)

    def delete_pdf_asset(self, paper_id: str) -> bool:
        with self._lock:
            return self.pdf_cache.delete(paper_id, save=True)

    # -------- Translate cache (thread-safe wrapper) --------
    def get_translate_asset(self, paper_id: str) -> Optional[TranslateAsset]:
        with self._lock:
            return self.translate_cache.get(paper_id)

    def upsert_translate_asset(self, asset: TranslateAsset) -> TranslateAsset:
        with self._lock:
            return self.translate_cache.upsert(asset, save=True)

    def update_translate_asset(
        self, paper_id: str, **kwargs
    ) -> Optional[TranslateAsset]:
        with self._lock:
            return self.translate_cache.update(paper_id, save=True, **kwargs)

    def delete_translate_asset(self, paper_id: str) -> bool:
        with self._lock:
            return self.translate_cache.delete(paper_id, save=True)

    # -------- tasks --------
    def create_translate_task(
        self,
        session_id: str,
        paper_id: str,
        input_pdf_url: Optional[str] = None,
        meta: Optional[Dict[str, str]] = None,
    ) -> TranslateTask:
        task_id = uuid.uuid4().hex
        t = TranslateTask(
            task_id=task_id,
            session_id=session_id,
            paper_id=paper_id,
            input_pdf_url=input_pdf_url,
            status="PENDING",
            meta=meta or {},
        )
        with self._lock:
            self.tasks[task_id] = t
        return t

    def get_task(self, task_id: str) -> Optional[TranslateTask]:
        with self._lock:
            return self.tasks.get(task_id)

    def update_task(self, task_id: str, **kwargs) -> Optional[TranslateTask]:
        with self._lock:
            t = self.tasks.get(task_id)
            if not t:
                return None
            for k, v in kwargs.items():
                setattr(t, k, v)
            t.updated_at = datetime.now()
            self.tasks[task_id] = t
            return t

    def list_tasks(
        self, session_id: Optional[str] = None, limit: int = 50
    ) -> List[TranslateTask]:
        with self._lock:
            tasks = list(self.tasks.values())
        if session_id:
            tasks = [t for t in tasks if t.session_id == session_id]
        tasks.sort(key=lambda x: x.updated_at, reverse=True)
        return tasks[: max(1, int(limit))]


store = InMemoryStore()
