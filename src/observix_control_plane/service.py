from __future__ import annotations

import hashlib
import json

from observix_common.models import AssignmentsResponse, Assignment


def compute_etag(assignments: list[Assignment]) -> str:
    payload = [
        {
            "assignment_id": a.assignment_id,
            "pipeline_id": a.pipeline.pipeline_id,
            "revision": a.revision,
        }
        for a in assignments
    ]
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_assignments_response(
    agent_id: str, region: str, assignments: list[Assignment]
) -> AssignmentsResponse:
    return AssignmentsResponse(
        agent_id=agent_id,
        region=region,
        assignments=assignments,
        etag=compute_etag(assignments),
    )
