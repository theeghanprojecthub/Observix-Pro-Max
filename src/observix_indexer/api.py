from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from observix_common.logging import setup_logging
from observix_indexer.engine import normalize

log = setup_logging("observix.indexer")

app = FastAPI(title="Observix Indexer", version="0.1.0")


class NormalizeRequest(BaseModel):
    profile: str = "passthrough"
    raw: str


@app.get("/v1/health")
def health():
    return {"ok": True}


@app.post("/v1/normalize")
def normalize_api(req: NormalizeRequest):
    try:
        doc = normalize(req.profile, req.raw)
        return {"ok": True, "doc": doc}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
