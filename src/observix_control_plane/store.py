from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from observix_common.ids import new_id
from observix_common.time import utcnow
from observix_common.models import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    PipelineSpec,
    Assignment,
)


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert_agent(
        self, req: AgentRegisterRequest, token: str
    ) -> AgentRegisterResponse:
        now = utcnow().isoformat()

        self.conn.execute(
            """
            INSERT INTO agents(agent_id, region, token, admin_port, capabilities, registered_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
              region=excluded.region,
              token=excluded.token,
              admin_port=excluded.admin_port,
              capabilities=excluded.capabilities;
            """,
            (
                req.agent_id,
                req.region,
                token,
                req.admin_port,
                json.dumps(req.capabilities),
                now,
            ),
        )
        self.conn.commit()
        return AgentRegisterResponse(
            agent_id=req.agent_id,
            token=token,
            registered_at=datetime.fromisoformat(now),
        )

    def get_agent_token(self, agent_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT token FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
        return row["token"] if row else None

    def create_pipeline(self, spec: PipelineSpec) -> PipelineSpec:
        self.conn.execute(
            "INSERT INTO pipelines(pipeline_id, name, spec_json) VALUES (?, ?, ?)",
            (spec.pipeline_id, spec.name, spec.model_dump_json()),
        )
        self.conn.commit()
        return spec

    def get_pipeline(self, pipeline_id: str) -> PipelineSpec | None:
        row = self.conn.execute(
            "SELECT spec_json FROM pipelines WHERE pipeline_id=?", (pipeline_id,)
        ).fetchone()
        if not row:
            return None
        return PipelineSpec.model_validate_json(row["spec_json"])

    def create_or_bump_assignment(
        self, agent_id: str, region: str, pipeline_id: str
    ) -> Assignment:
        now = utcnow().isoformat()
        existing = self.conn.execute(
            "SELECT assignment_id, revision FROM assignments WHERE agent_id=? AND pipeline_id=?",
            (agent_id, pipeline_id),
        ).fetchone()

        if existing:
            assignment_id = existing["assignment_id"]
            revision = int(existing["revision"]) + 1
            self.conn.execute(
                "UPDATE assignments SET revision=?, updated_at=? WHERE assignment_id=?",
                (revision, now, assignment_id),
            )
        else:
            assignment_id = new_id("asgn")
            revision = 1
            self.conn.execute(
                """
                INSERT INTO assignments(assignment_id, agent_id, region, pipeline_id, revision, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (assignment_id, agent_id, region, pipeline_id, revision, now),
            )

        self.conn.commit()

        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_id}")

        return Assignment(
            assignment_id=assignment_id,
            agent_id=agent_id,
            region=region,
            pipeline=pipeline,
            revision=revision,
            updated_at=datetime.fromisoformat(now),
        )

    def list_assignments_for_agent(
        self, agent_id: str, region: str
    ) -> list[Assignment]:
        rows = self.conn.execute(
            """
            SELECT a.assignment_id, a.pipeline_id, a.revision, a.updated_at
            FROM assignments a
            WHERE a.agent_id=? AND a.region=?
            ORDER BY a.assignment_id
            """,
            (agent_id, region),
        ).fetchall()

        out: list[Assignment] = []
        for r in rows:
            pipeline = self.get_pipeline(r["pipeline_id"])
            if not pipeline:
                continue
            out.append(
                Assignment(
                    assignment_id=r["assignment_id"],
                    agent_id=agent_id,
                    region=region,
                    pipeline=pipeline,
                    revision=int(r["revision"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
            )
        return out
