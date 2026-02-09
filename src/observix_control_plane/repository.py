from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from observix_control_plane.models import Agent, Assignment, Pipeline


def upsert_agent(
    session: Session,
    agent_id: str,
    region: str,
    tenant_id: Optional[str],
    admin_port: Optional[int],
    capabilities: Dict[str, Any],
) -> Agent:
    a = session.get(Agent, agent_id)
    now = datetime.utcnow()
    if a is None:
        a = Agent(
            id=agent_id,
            region=region,
            tenant_id=tenant_id,
            admin_port=admin_port,
            capabilities=capabilities,
            created_at=now,
            last_seen_at=now,
        )
        session.add(a)
        session.flush()
        return a

    a.region = region
    a.tenant_id = tenant_id
    a.admin_port = admin_port
    a.capabilities = capabilities
    a.last_seen_at = now
    session.flush()
    return a


def create_pipeline(
    session: Session, name: str, enabled: bool, spec: Dict[str, Any]
) -> Pipeline:
    p = Pipeline(name=name, enabled=enabled, spec=spec, version=1)
    session.add(p)
    session.flush()
    return p


def update_pipeline(
    session: Session, pipeline_id: str, name: str, enabled: bool, spec: Dict[str, Any]
) -> Pipeline:
    p = session.get(Pipeline, pipeline_id)
    if p is None:
        raise KeyError("pipeline_not_found")
    p.name = name
    p.enabled = enabled
    p.spec = spec
    p.version = int(p.version) + 1
    p.updated_at = datetime.utcnow()
    session.flush()
    return p


def list_pipelines(session: Session) -> List[Pipeline]:
    return list(
        session.scalars(select(Pipeline).order_by(Pipeline.created_at.desc())).all()
    )


def create_assignment(
    session: Session, agent_id: str, region: str, pipeline_id: str
) -> Assignment:
    a = Assignment(agent_id=agent_id, region=region, pipeline_id=pipeline_id)
    session.add(a)
    session.flush()
    return a


def list_assignments(session: Session) -> List[Assignment]:
    return list(
        session.scalars(select(Assignment).order_by(Assignment.created_at.desc())).all()
    )


def get_agent_assignments(
    session: Session, agent_id: str, region: str
) -> Tuple[str, List[Dict[str, Any]]]:
    q = (
        select(Assignment, Pipeline)
        .join(Pipeline, Pipeline.id == Assignment.pipeline_id)
        .where(Assignment.agent_id == agent_id)
        .where(Assignment.region == region)
        .order_by(Assignment.created_at.asc())
    )
    rows = session.execute(q).all()

    assignments: List[Dict[str, Any]] = []
    for asn, pipe in rows:
        pipe_spec = dict(pipe.spec)
        pipe_spec["pipeline_id"] = pipe.id
        pipe_spec["name"] = pipe.name
        pipe_spec["enabled"] = pipe.enabled
        pipe_spec["version"] = pipe.version
        assignments.append(
            {
                "assignment_id": asn.id,
                "agent_id": asn.agent_id,
                "region": asn.region,
                "pipeline": pipe_spec,
            }
        )

    etag_src = "|".join(
        f"{a['pipeline']['pipeline_id']}:{a['pipeline']['version']}:{int(a['pipeline']['enabled'])}"
        for a in assignments
    )
    etag = hashlib.sha256(etag_src.encode("utf-8")).hexdigest()
    return etag, assignments
