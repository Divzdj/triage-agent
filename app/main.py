import os
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import TriageRequest, TriageResponse
from app.agent import TriageAgent

app = FastAPI(title="Support Ticket Triage Agent")


# --- Environment Config ---
KB_PATH = os.getenv("KB_PATH", "kb/kb.json")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

agent = TriageAgent(kb_path=KB_PATH, openai_api_key=OPENAI_API_KEY, model_name=MODEL)


# --- SIMPLE RATE LIMITER ---
RATE_LIMIT_REQUESTS = 10     # allowed requests
RATE_LIMIT_WINDOW = 60       # time window (sec)
rate_limiter = {}            # IP → [timestamps]


def is_rate_limited(ip: str) -> bool:
    """
    Simple in-memory rate limiter using timestamp buckets.
    Allows RATE_LIMIT_REQUESTS per RATE_LIMIT_WINDOW seconds.
    """
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    if ip not in rate_limiter:
        rate_limiter[ip] = []

    # keep timestamps within the window
    rate_limiter[ip] = [t for t in rate_limiter[ip] if t > window_start]

    # deny if limit exceeded
    if len(rate_limiter[ip]) >= RATE_LIMIT_REQUESTS:
        return True

    # record current request
    rate_limiter[ip].append(now)
    return False


# --- UI STATIC FILES ---
app.mount("/ui", StaticFiles(directory="ui"), name="ui")

@app.get("/")
def root():
    """
    Serves the UI HTML file
    """
    return FileResponse("ui/index.html")



# --- API ENDPOINT ---
@app.post("/triage", response_model=TriageResponse)
async def triage(req: TriageRequest, request: Request):
    # RATE LIMIT CHECK
    client_ip = request.client.host
    if is_rate_limited(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds."
        )

    # VALIDATION
    if not req.description or not req.description.strip():
        raise HTTPException(status_code=400, detail="description cannot be empty")

    # TRIAGE PROCESSING
    try:
        result = agent.triage_ticket(req.description)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
