"""
Vercel serverless function that wraps the eyewear agent.

This file is the BACKEND that Lovable will call. Every request the user sends
in the Lovable chat hits this endpoint.

Architecture:
- POST /api/chat with {message, history}
- Returns {reply, recommended_ids, intent, path}
- The OpenAI key lives in Vercel env vars, NOT in the browser
- CORS is enabled so Lovable's domain can call this

Deployment: Vercel auto-detects FastAPI when this file lives in /api
"""

import json
import os
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Make agent.py importable - it's in the parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import generate_response, load_catalog  # noqa: E402

# ---------- App Setup ----------
app = FastAPI()

# CORS: allow Lovable's domain to call this API.
# We start permissive ("*") for the demo; in production you'd lock to your Lovable URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------- Catalog Cache ----------
# Vercel functions can be "warm" between requests, so we cache the catalog
# in module scope. First call loads it; subsequent calls reuse it.
_CATALOG = None
def get_catalog():
    global _CATALOG
    if _CATALOG is None:
        catalog_path = Path(__file__).resolve().parent.parent / "lenskart_catalogue.json"
        _CATALOG = load_catalog(str(catalog_path))
    return _CATALOG


# ---------- Simple In-Memory Rate Limit ----------
# Prevents one visitor from burning through your OpenAI credits.
# 30 requests per IP per hour. In-memory means it resets on cold start,
# which is fine for a portfolio demo. For production: use Vercel KV or Redis.
_REQUEST_LOG = defaultdict(deque)
_RATE_LIMIT = 30          # requests
_RATE_WINDOW = 3600       # seconds (1 hour)


def check_rate_limit(ip: str) -> bool:
    """Returns True if request allowed, False if rate limited."""
    now = time.time()
    log = _REQUEST_LOG[ip]
    # Drop requests older than the window
    while log and now - log[0] > _RATE_WINDOW:
        log.popleft()
    if len(log) >= _RATE_LIMIT:
        return False
    log.append(now)
    return True


# ---------- Request/Response Schemas ----------
class Message(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    reply: str
    recommended_ids: list[str] = []
    intent: dict = {}
    path: str = "unknown"


# ---------- Endpoints ----------
@app.get("/api/health")
async def health():
    """Sanity check that the backend is running."""
    return {
        "status": "ok",
        "catalog_size": len(get_catalog()),
        "openai_key_configured": bool(os.environ.get("OPENAI_API_KEY")),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    """Main chat endpoint - this is what Lovable calls on every user turn."""
    # Get the user's IP for rate limiting (best-effort; behind a proxy may show proxy IP)
    client_ip = http_request.client.host if http_request.client else "unknown"
    if "x-forwarded-for" in http_request.headers:
        client_ip = http_request.headers["x-forwarded-for"].split(",")[0].strip()

    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({_RATE_LIMIT} requests/hour). Try again later."
        )

    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY not configured on the backend."
        )

    catalog = get_catalog()
    history_dicts = [{"role": m.role, "content": m.content} for m in request.history]

    try:
        result = generate_response(request.message, history_dicts, catalog)
        return ChatResponse(
            reply=result["reply"],
            recommended_ids=result.get("recommended_ids", []),
            intent=result.get("intent", {}),
            path=result.get("path", "unknown"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.get("/api/catalog")
async def catalog():
    """Returns the full catalog so the frontend can display product cards
    after the agent responds with product_ids."""
    return get_catalog()


@app.get("/api/eval-results")
async def eval_results():
    """Returns the latest eval_results.json if present, so the eval page
    can render without bundling the file in the frontend."""
    path = Path(__file__).resolve().parent.parent / "eval_results.json"
    if not path.exists():
        return {"error": "eval_results.json not found - run python eval_harness.py first"}
    with open(path) as f:
        return json.load(f)
