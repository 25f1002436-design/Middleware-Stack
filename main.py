import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

EMAIL = "25f1002436@ds.study.iitm.ac.in"
ALLOWED_ORIGIN = "https://app-mjddm5.example.com"
EXAM_ORIGIN = "PASTE_EXAM_PAGE_ORIGIN_HERE"  # e.g. https://something.example.com (no trailing slash, no path)

LIMIT = 13
WINDOW = 10.0  # seconds

hits = defaultdict(deque)

app = FastAPI()


# Middleware order: the LAST one added is the OUTERMOST.
# Request flow: CORS -> request context -> rate limit -> endpoint.
# CORS is outermost so even 429 responses carry the CORS headers
# (otherwise the browser hides the 429 from the grader).

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    client = request.headers.get("X-Client-Id") or "anonymous"
    now = time.monotonic()
    q = hits[client]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        retry = max(1, int(WINDOW - (now - q[0])) + 1)
        return JSONResponse(
            {"detail": "Too Many Requests",
             "request_id": getattr(request.state, "request_id", None)},
            status_code=429,
            headers={"Retry-After": str(retry)},
        )
    q.append(now)
    return await call_next(request)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN, EXAM_ORIGIN],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["X-Request-ID", "X-Client-Id", "Content-Type"],
    expose_headers=["X-Request-ID"],
    allow_credentials=False,
)


@app.get("/ping")
def ping(request: Request):
    return {"email": EMAIL, "request_id": request.state.request_id}
