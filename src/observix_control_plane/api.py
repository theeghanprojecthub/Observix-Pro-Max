"""
Observix Control Plane API.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from observix_control_plane.db import get_engine, session_scope, init_engine
from observix_control_plane.db_bootstrap import ensure_tables
from observix_control_plane.models import Agent, Assignment, Pipeline
from observix_common.logging import setup_logging
from observix_common.models import (
    AgentRegisterRequest,
    AssignmentsResponse,
    Assignment as AssignmentDTO,
    PipelineDestination,
    PipelineProcessor,
    PipelineSource,
    PipelineSpec,
)

log = setup_logging("observix.control_plane")


class Settings(BaseModel):
    """Control plane settings loaded from YAML."""

    host: str = "127.0.0.1"
    port: int = 7000
    allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    agent_offline_threshold_seconds: int = 20
    database_url: Optional[str] = None


class HeartbeatRequest(BaseModel):
    """Agent heartbeat payload."""

    region: str
    admin_port: Optional[int] = None
    capabilities: List[str] = Field(default_factory=list)


class PipelineCreateRequest(BaseModel):
    """Create pipeline request.

    Note:
      - `spec` should contain the runtime spec: source/processor/destination/batching.
      - pipeline_id/name/enabled/version are controlled by control-plane DB fields.
    """

    name: str
    enabled: bool = True
    spec: Dict[str, Any]


class PipelineUpdateRequest(BaseModel):
    """Update pipeline request."""

    name: str
    enabled: bool
    spec: Dict[str, Any]


class PipelineResponse(BaseModel):
    """Pipeline response."""

    pipeline_id: str
    name: str
    enabled: bool
    version: int
    spec: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AssignmentCreateRequest(BaseModel):
    """Assign pipeline to agent."""

    agent_id: str
    region: str
    pipeline_id: str


class AssignmentResponse(BaseModel):
    """Assignment response."""

    assignment_id: str
    agent_id: str
    region: str
    pipeline_id: str
    created_at: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _etag(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _agent_live_status(last_seen_at: datetime, threshold_seconds: int) -> str:
    now = _utcnow()
    if now - last_seen_at <= timedelta(seconds=threshold_seconds):
        return "ONLINE"
    return "OFFLINE"


def _upsert_agent(session: Session, req: AgentRegisterRequest) -> Agent:
    now = _utcnow()
    row = session.get(Agent, req.agent_id)
    if row is None:
        row = Agent(
            id=req.agent_id,
            region=req.region,
            tenant_id=getattr(req, "tenant_id", None),
            admin_port=req.admin_port,
            capabilities={"items": req.capabilities},
            created_at=now,
            last_seen_at=now,
        )
        session.add(row)
        return row

    row.region = req.region
    row.admin_port = req.admin_port
    row.capabilities = {"items": req.capabilities}
    row.last_seen_at = now
    return row


def _touch_agent(session: Session, agent_id: str) -> Agent:
    row = session.get(Agent, agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail="agent_not_found")
    row.last_seen_at = _utcnow()
    return row


def _normalize_pipeline_spec_dict(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize pipeline spec into canonical shape:

      canonical:
        {"source": {...}, "processor": {...}, "destination": {...}, ...}

    Backwards compatible with accidental wrappers seen in the wild:
      {"spec": {...}} or {"spec": {"spec": {...}}}

    We only unwrap when the current level does not already look canonical.
    """
    cur: Any = dict(spec or {})

    for _ in range(2):  # unwrap up to 2 levels to cover spec.spec
        if not isinstance(cur, dict):
            return {}

        looks_canonical = (
            ("source" in cur) or ("destination" in cur) or ("processor" in cur)
        )
        if looks_canonical:
            return cur

        inner = cur.get("spec")
        if isinstance(inner, dict):
            cur = inner
            continue

        return cur if isinstance(cur, dict) else {}

    return cur if isinstance(cur, dict) else {}


def _sanitize_pipeline_spec_dict(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys that should NOT live inside the DB spec blob."""
    cleaned = _normalize_pipeline_spec_dict(spec)

    cleaned.pop("pipeline_id", None)
    cleaned.pop("name", None)
    cleaned.pop("enabled", None)
    cleaned.pop("version", None)

    return cleaned


def _to_pipeline_spec(pipe: Pipeline) -> PipelineSpec:
    """Map DB Pipeline -> common PipelineSpec (agent contract)."""
    spec = _normalize_pipeline_spec_dict(dict(pipe.spec or {}))

    # Required sections
    source_dict = spec.get("source") or {}
    destination_dict = spec.get("destination") or {}

    # Processor is optional in the schema but in your model it exists (default raw).
    processor_dict = spec.get("processor") or {"mode": "raw", "options": {}}

    # If a stored pipeline is invalid, fail cleanly (avoid 500 pydantic crashes)
    if not source_dict or not destination_dict:
        raise HTTPException(
            status_code=500,
            detail="pipeline_spec_invalid_missing_source_or_destination",
        )

    return PipelineSpec(
        pipeline_id=pipe.id,
        name=pipe.name,
        enabled=pipe.enabled,
        source=PipelineSource(**source_dict),
        processor=PipelineProcessor(**processor_dict),
        destination=PipelineDestination(**destination_dict),
        batch_max_events=int(spec.get("batch_max_events", 200)),
        batch_max_seconds=float(spec.get("batch_max_seconds", 1.0)),
    )


def create_app(settings: Settings) -> FastAPI:
    """Create the control plane FastAPI app."""
    app = FastAPI(title="Observix Control Plane", version="0.1.0")

    @app.on_event("startup")
    def _startup() -> None:
        init_engine(settings.database_url)
        ensure_tables(get_engine())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> Dict[str, Any]:
        return {"ok": True}

    @app.post("/v1/agents/register")
    def register_agent(req: AgentRegisterRequest) -> Dict[str, Any]:
        with session_scope() as session:
            _upsert_agent(session, req)
        log.info(f"agent_registered agent_id={req.agent_id} region={req.region}")
        return {"ok": True}

    @app.post("/v1/agents/{agent_id}/heartbeat")
    def heartbeat(agent_id: str, req: HeartbeatRequest) -> Dict[str, Any]:
        with session_scope() as session:
            row = session.get(Agent, agent_id)
            if row is None:
                raise HTTPException(status_code=404, detail="agent_not_found")
            row.region = req.region
            row.admin_port = req.admin_port
            row.capabilities = {"items": req.capabilities}
            row.last_seen_at = _utcnow()
        return {"ok": True}

    @app.get("/v1/agents")
    def list_agents() -> Dict[str, Any]:
        with session_scope() as session:
            rows = (
                session.execute(select(Agent).order_by(Agent.created_at.asc()))
                .scalars()
                .all()
            )
            items: List[Dict[str, Any]] = []
            for a in rows:
                items.append(
                    {
                        "agent_id": a.id,
                        "region": a.region,
                        "tenant_id": a.tenant_id,
                        "admin_port": a.admin_port,
                        "capabilities": a.capabilities,
                        "created_at": a.created_at,
                        "last_seen_at": a.last_seen_at,
                        "status": _agent_live_status(
                            a.last_seen_at, settings.agent_offline_threshold_seconds
                        ),
                    }
                )
            return {"agents": items}

    @app.get("/v1/agents/{agent_id}/assignments")
    def get_assignments(
        agent_id: str, region: str, response: Response
    ) -> AssignmentsResponse:
        """
        IMPORTANT: This must return `AssignmentsResponse(assignments: list[Assignment])`
        where Assignment is the common model (agent-facing contract), NOT raw dicts.
        """
        with session_scope() as session:
            _touch_agent(session, agent_id)

            rows = session.execute(
                select(Assignment, Pipeline)
                .join(Pipeline, Pipeline.id == Assignment.pipeline_id)
                .where(Assignment.agent_id == agent_id)
                .where(Assignment.region == region)
                .order_by(Assignment.created_at.asc())
            ).all()

            assignments: List[AssignmentDTO] = []
            etag_basis: List[Dict[str, Any]] = []

            for asg, pipe in rows:
                pipeline_spec = _to_pipeline_spec(pipe)

                assignments.append(
                    AssignmentDTO(
                        assignment_id=asg.id,
                        agent_id=asg.agent_id,
                        region=asg.region,
                        pipeline=pipeline_spec,
                        revision=int(pipe.version),
                        updated_at=pipe.updated_at,
                    )
                )

                etag_basis.append(
                    {
                        "assignment_id": asg.id,
                        "pipeline_id": pipe.id,
                        "version": int(pipe.version),
                        "updated_at": str(pipe.updated_at),
                    }
                )

            et = _etag(etag_basis)
            response.headers["ETag"] = et

            return AssignmentsResponse(
                agent_id=agent_id,
                region=region,
                etag=et,
                assignments=assignments,
            )

    @app.post("/v1/pipelines")
    def create_pipeline(req: PipelineCreateRequest) -> Dict[str, Any]:
        now = _utcnow()
        cleaned_spec = _sanitize_pipeline_spec_dict(req.spec)

        row = Pipeline(
            name=req.name,
            enabled=req.enabled,
            version=1,
            spec=cleaned_spec,
            created_at=now,
            updated_at=now,
        )
        with session_scope() as session:
            session.add(row)
            session.flush()
            pipeline_id = row.id
        return {"pipeline_id": pipeline_id}

    @app.put("/v1/pipelines/{pipeline_id}")
    def update_pipeline(pipeline_id: str, req: PipelineUpdateRequest) -> Dict[str, Any]:
        with session_scope() as session:
            row = session.get(Pipeline, pipeline_id)
            if row is None:
                raise HTTPException(status_code=404, detail="pipeline_not_found")

            row.name = req.name
            row.enabled = req.enabled
            row.spec = _sanitize_pipeline_spec_dict(req.spec)
            row.version = int(row.version) + 1
            row.updated_at = _utcnow()

        return {"ok": True}

    @app.get("/v1/pipelines")
    def list_pipelines() -> Dict[str, Any]:
        with session_scope() as session:
            rows = (
                session.execute(select(Pipeline).order_by(Pipeline.created_at.asc()))
                .scalars()
                .all()
            )
            items = [
                PipelineResponse(
                    pipeline_id=p.id,
                    name=p.name,
                    enabled=p.enabled,
                    version=p.version,
                    spec=p.spec,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                ).model_dump(mode="json")
                for p in rows
            ]
            return {"pipelines": items}

    @app.post("/v1/assignments")
    def create_assignment(req: AssignmentCreateRequest) -> Dict[str, Any]:
        with session_scope() as session:
            agent = session.get(Agent, req.agent_id)
            if agent is None:
                raise HTTPException(status_code=404, detail="agent_not_found")
            pipe = session.get(Pipeline, req.pipeline_id)
            if pipe is None:
                raise HTTPException(status_code=404, detail="pipeline_not_found")

            existing = (
                session.execute(
                    select(Assignment)
                    .where(Assignment.agent_id == req.agent_id)
                    .where(Assignment.region == req.region)
                    .where(Assignment.pipeline_id == req.pipeline_id)
                )
                .scalars()
                .first()
            )

            if existing is not None:
                return {"assignment_id": existing.id}

            asg = Assignment(
                agent_id=req.agent_id,
                region=req.region,
                pipeline_id=req.pipeline_id,
                created_at=_utcnow(),
            )
            session.add(asg)
            session.flush()
            return {"assignment_id": asg.id}

    @app.delete("/v1/assignments/{assignment_id}")
    def delete_assignment(assignment_id: str) -> Dict[str, Any]:
        with session_scope() as session:
            row = session.get(Assignment, assignment_id)
            if row is None:
                raise HTTPException(status_code=404, detail="assignment_not_found")
            session.delete(row)
        return {"ok": True}

    return app
