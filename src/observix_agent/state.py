from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class AgentState:
    def __init__(self, state_dir: str):
        self.root = Path(state_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._token_path = self.root / "agent_token.json"
        self._offsets_path = self.root / "offsets.json"

    def load_token(self) -> str | None:
        if not self._token_path.exists():
            return None
        data = json.loads(self._token_path.read_text(encoding="utf-8"))
        return data.get("token")

    def save_token(self, token: str) -> None:
        self._token_path.write_text(json.dumps({"token": token}), encoding="utf-8")

    def load_offsets(self) -> Dict[str, int]:
        if not self._offsets_path.exists():
            return {}
        return json.loads(self._offsets_path.read_text(encoding="utf-8"))

    def save_offsets(self, offsets: Dict[str, int]) -> None:
        self._offsets_path.write_text(json.dumps(offsets), encoding="utf-8")
