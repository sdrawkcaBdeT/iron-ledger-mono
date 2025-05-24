# economy_sim/sidecar/api.py
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from .schemas import RoundConfigOut, GatherRunIn
from .tool_calc import compute_round_config, apply_gather_use

app = FastAPI(title="Arena Side-Car", version="0.1.0")
_API_KEY = "local-dev-only"

# example assignment table
_AGENT_TOOL = {17: ("steel_hatchet", "Refined")}

@app.get("/v1/round_config", response_model=RoundConfigOut)
def round_config(x_api_key: str = Header(...), agent_id: int = 17):
    if x_api_key != _API_KEY:
        raise HTTPException(401, "Bad key")
    tool_id, qual_id = _AGENT_TOOL[agent_id]
    return compute_round_config(agent_id, tool_id, qual_id)

@app.post("/v1/submit_gather")
def submit_gather(payload: GatherRunIn, x_api_key: str = Header(...)):
    if x_api_key != _API_KEY:
        raise HTTPException(401, "Bad key")
    cfg   = round_config(x_api_key=_API_KEY, agent_id=payload.agent_id)
    res   = apply_gather_use(cfg, payload.nodes_collected)
    return JSONResponse(res.dict())
