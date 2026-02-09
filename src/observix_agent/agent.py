"""
Observix Agent runtime.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List

import httpx

from observix_common.logging import setup_logging
from observix_common.models import (
    AgentRegisterRequest,
    AssignmentsResponse,
    PipelineSpec,
)
from observix_agent.pipeline import PipelineRunner, Runtime
from observix_agent.retry import RetryPolicy
from observix_agent.state import AgentState

log = setup_logging("observix.agent")


class Agent:
    """Agent process that registers, heartbeats, pulls assignments, and runs pipelines."""

    def __init__(
        self,
        agent_id: str,
        region: str,
        tenant_id: str | None,
        admin_port: int | None,
        control_plane_url: str,
        poll_assignments_seconds: int,
        state_dir: str,
    ):
        self.agent_id = agent_id
        self.region = region
        self.tenant_id = tenant_id
        self.admin_port = admin_port
        self.control_plane_url = control_plane_url.rstrip("/")
        self.poll_assignments_seconds = poll_assignments_seconds

        self.state = AgentState(state_dir)
        self._etag: str | None = None

        self._lock = threading.Lock()
        self._pipelines: Dict[str, PipelineRunner] = {}

        self.retry = RetryPolicy()

        self._heartbeat_seconds = 5
        self._http_timeout_seconds = 5.0

    def _capabilities(self) -> List[str]:
        return [
            "file_tail",
            "syslog_udp",
            "http_listener",
            "http",
            "file",
            "syslog_udp_dest",
        ]

    def register(self) -> None:
        req = AgentRegisterRequest(
            agent_id=self.agent_id,
            region=self.region,
            admin_port=self.admin_port,
            capabilities=self._capabilities(),
        )
        with httpx.Client(timeout=self._http_timeout_seconds) as client:
            r = client.post(
                f"{self.control_plane_url}/v1/agents/register",
                json=req.model_dump(mode="json"),
            )
            r.raise_for_status()
        log.info(f"registered agent_id={self.agent_id} region={self.region}")

    def heartbeat(self) -> None:
        payload = {
            "region": self.region,
            "admin_port": self.admin_port,
            "capabilities": self._capabilities(),
        }
        with httpx.Client(timeout=self._http_timeout_seconds) as client:
            r = client.post(
                f"{self.control_plane_url}/v1/agents/{self.agent_id}/heartbeat",
                json=payload,
            )
            r.raise_for_status()

    def pull_assignments(self) -> AssignmentsResponse:
        with httpx.Client(timeout=self._http_timeout_seconds) as client:
            r = client.get(
                f"{self.control_plane_url}/v1/agents/{self.agent_id}/assignments",
                params={"region": self.region},
            )
            r.raise_for_status()
            return AssignmentsResponse.model_validate(r.json())

    def _spec_to_runner_input(self, spec: PipelineSpec) -> Any:
        """
        PipelineRunner implementations often expect dict-like specs.
        Convert Pydantic models to plain dict for compatibility.
        """
        # Pydantic v2 models have model_dump
        if hasattr(spec, "model_dump"):
            return spec.model_dump(mode="python")
        return spec

    def _apply_assignments(self, resp: AssignmentsResponse) -> None:
        if self._etag == resp.etag:
            return
        self._etag = resp.etag

        # Keep only enabled pipelines
        new_specs: Dict[str, PipelineSpec] = {
            a.pipeline.pipeline_id: a.pipeline
            for a in resp.assignments
            if a.pipeline.enabled
        }

        with self._lock:
            # remove runners no longer assigned
            for pid in list(self._pipelines.keys()):
                if pid not in new_specs:
                    del self._pipelines[pid]

            # add new runners
            for pid, spec in new_specs.items():
                if pid in self._pipelines:
                    continue

                rt = Runtime(
                    agent_id=self.agent_id,
                    region=self.region,
                    tenant_id=self.tenant_id,
                    state=self.state,
                )

                # ✅ critical: pass dict to PipelineRunner unless it natively supports the model
                runner_spec = self._spec_to_runner_input(spec)

                self._pipelines[pid] = PipelineRunner(rt, runner_spec, self.retry)

        log.info(
            f"assignments_applied agent_id={self.agent_id} pipelines={len(self._pipelines)}"
        )

    def run_forever(self) -> None:
        self.register()

        last_pull = 0.0
        last_hb = 0.0

        while True:
            now = time.monotonic()

            if (now - last_hb) >= self._heartbeat_seconds:
                try:
                    self.heartbeat()
                except Exception:
                    # ✅ show real error + line
                    log.exception("heartbeat_failed")
                last_hb = now

            if (now - last_pull) >= self.poll_assignments_seconds:
                try:
                    resp = self.pull_assignments()
                    self._apply_assignments(resp)
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status == 404:
                        try:
                            self.register()
                        except Exception:
                            log.exception("re_register_failed")
                    else:
                        log.warning("assignments_pull_failed status=%s", status)
                except Exception:
                    # ✅ show real error + line (your previous TypeError will now show the stack)
                    log.exception("assignments_pull_failed")
                last_pull = now

            with self._lock:
                runners = list(self._pipelines.values())

            for r in runners:
                try:
                    r.tick()
                except Exception:
                    # ✅ if tick fails you see it (previously this could crash silently)
                    log.exception("pipeline_tick_failed")

            time.sleep(0.05)
