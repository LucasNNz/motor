from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    width: int = 768
    height: int = 768
    steps: int = 1
    seed: Optional[int] = None
    backend: str = "composer"
    engine_url: Optional[str] = None


class BatchStartRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Plain text or TXT contents. One prompt per line or ID|prompt.")
    width: int = 768
    height: int = 768
    steps: int = 1
    backend: str = "composer"
    engine_url: Optional[str] = None
    output_prefix: str = "img"


class BatchItem(BaseModel):
    id: str
    prompt: str
    status: Literal["pending", "running", "done", "error", "cancelled"] = "pending"
    output_file: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    composition: Optional[Dict[str, Any]] = None
    operation_id: Optional[str] = None
    export_url: Optional[str] = None


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


class CollectRequest(BaseModel):
    query: str = Field(..., min_length=1)
    type: Literal["background", "object", "pose", "face", "outfit", "character", "other"] = "object"
    concept: Optional[str] = None
    providers: List[str] = Field(default_factory=lambda: ["openverse", "wikimedia_commons"])
    per_provider: int = 8
    save_limit: int = 5
    auto_approve: bool = False


class CollectMissingRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    providers: List[str] = Field(default_factory=lambda: ["openverse", "wikimedia_commons"])
    per_provider: int = 8
    save_limit_per_concept: int = 3
    auto_approve: bool = False


class MemoryApproveRequest(BaseModel):
    approved: bool = True


class RefinerBenchmarkRequest(BaseModel):
    backend: Literal["light_cpu", "sdcpp_img2img"] = "sdcpp_img2img"
    prompts: Optional[List[str]] = None
    width: int = 512
    height: int = 512
    steps: int = 3
    strength: float = 0.24


class GuidedCollectRequest(BaseModel):
    guide_text: str = Field(..., min_length=1)
    providers: List[str] = Field(default_factory=lambda: ["openverse", "wikimedia_commons"])
    auto_approve: bool = False


class GuidedGenerateRequest(BaseModel):
    prompt: str = ""
    guide_text: str = Field(..., min_length=1)
    width: int = 768
    height: int = 768
    refiner: Literal["none", "light_cpu", "sdcpp_img2img"] = "none"
    steps: int = 3
    strength: float = 0.24
    collect_missing: bool = False
    auto_approve_collected: bool = False


class MemoryUpdateRequest(BaseModel):
    status: Optional[Literal["candidates", "approved", "rejected"]] = None
    tags: Optional[List[str]] = None
    preferred: Optional[bool] = None
    blocked: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    type: Optional[str] = None
    concept: Optional[str] = None


class OperationEvaluationRequest(BaseModel):
    approved: Optional[bool] = None
    scores: Dict[str, Any] = Field(default_factory=dict)
    error_type: Optional[str] = None
    problem: Optional[str] = None
    severity: Optional[str] = None
    notes: Optional[str] = None

class OperationReprocessRequest(BaseModel):
    correction_guide_text: str = Field(..., min_length=1)
    refiner: Literal["light_cpu", "sdcpp_img2img"] = "light_cpu"
    steps: int = 3
    strength: float = 0.24

