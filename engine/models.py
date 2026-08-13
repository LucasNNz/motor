from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    width: int = 768
    height: int = 768
    steps: int = 4
    seed: Optional[int] = None
    backend: str = "mock"
    engine_url: Optional[str] = None


class BatchStartRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Plain text or TXT contents. One prompt per line or ID|prompt.")
    width: int = 768
    height: int = 768
    steps: int = 4
    backend: str = "mock"
    engine_url: Optional[str] = None
    output_prefix: str = "img"


class BatchItem(BaseModel):
    id: str
    prompt: str
    status: Literal["pending", "running", "done", "error", "cancelled"] = "pending"
    output_file: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


class BatchStatus(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error", "cancelled"]
    backend: str
    engine_url: Optional[str] = None
    width: int
    height: int
    steps: int
    items: List[BatchItem]
    started_at: float
    finished_at: Optional[float] = None
    total: int
    completed: int
    failed: int
    zip_ready: bool = False
