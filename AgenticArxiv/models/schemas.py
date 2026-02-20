# AgenticArxiv/models/schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict
from datetime import datetime

class Paper(BaseModel):
    id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    published: Optional[str] = None
    updated: Optional[str] = None
    pdf_url: Optional[str] = None
    primary_category: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    comment: Optional[str] = None
    links: List[str] = Field(default_factory=list)

class SessionState(BaseModel):
    session_id: str
    last_papers: List[Paper] = Field(default_factory=list)
    last_active_paper_id: Optional[str] = None
    last_active_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.now)

TaskStatus = Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]

class TranslateTask(BaseModel):
    task_id: str
    session_id: str
    paper_id: str
    status: TaskStatus = "PENDING"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    progress: float = 0.0
    input_pdf_url: Optional[str] = None
    input_pdf_path: Optional[str] = None
    output_pdf_path: Optional[str] = None
    error: Optional[str] = None
    meta: Dict[str, str] = Field(default_factory=dict)
