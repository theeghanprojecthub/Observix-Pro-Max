from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    agent_id: str
    region: str
    admin_port: Optional[int] = None
    capabilities: List[str] = Field(default_factory=list)
    token: Optional[str] = None


class PipelineSource(BaseModel):
    type: Literal["file_tail", "syslog_udp"]
    options: Dict[str, Any] = Field(default_factory=dict)


class PipelineProcessor(BaseModel):
    mode: Literal["raw", "indexed"] = "raw"
    options: Dict[str, Any] = Field(default_factory=dict)


class PipelineDestination(BaseModel):
    type: Literal["http", "syslog_udp", "file"]
    options: Dict[str, Any] = Field(default_factory=dict)


class PipelineSpec(BaseModel):
    pipeline_id: str
    name: str
    enabled: bool = True
    source: PipelineSource
    processor: PipelineProcessor = Field(default_factory=PipelineProcessor)
    destination: PipelineDestination
    batch_max_events: int = Field(200, ge=1)
    batch_max_seconds: float = Field(1.0, ge=0.1)


class Assignment(BaseModel):
    assignment_id: str
    agent_id: str
    region: str
    pipeline: PipelineSpec
    revision: int = Field(1, ge=1)
    updated_at: datetime


class AssignmentsResponse(BaseModel):
    etag: str
    assignments: list[Assignment]
    agent_id: str | None = None
    region: str | None = None


# If you want a clean create request that matches DB spec storage:
class CreatePipelineRequest(BaseModel):
    name: str
    enabled: bool = True
    source: PipelineSource
    processor: PipelineProcessor = Field(default_factory=PipelineProcessor)
    destination: PipelineDestination
    batch_max_events: int = Field(200, ge=1)
    batch_max_seconds: float = Field(1.0, ge=0.1)


class CreateAssignmentRequest(BaseModel):
    agent_id: str
    region: str
    pipeline_id: str


class LogEvent(BaseModel):
    ts: datetime
    tenant_id: Optional[str] = None
    region: str
    agent_id: str
    pipeline_id: str
    raw: str
    structured: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
