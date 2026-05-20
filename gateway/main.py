import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Prometheus Gateway",
    description="API gateway routing to classification (8001) and regression (8002) microservices",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLASSIFICATION_URL = "http://localhost:8001"
REGRESSION_URL = "http://localhost:8002"

_client = httpx.AsyncClient(timeout=600.0)


async def _proxy(request: Request, target_base: str, path: str) -> Response:
    url = f"{target_base}{path}"
    params = dict(request.query_params)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    body = await request.body()

    resp = await _client.request(
        method=request.method,
        url=url,
        params=params,
        headers=headers,
        content=body,
    )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


# ── Classification routes ────────────────────────────────────────────────────

@app.api_route("/classification/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def classification_proxy(request: Request, path: str):
    return await _proxy(request, CLASSIFICATION_URL, f"/{path}")


# ── Regression routes ────────────────────────────────────────────────────────

@app.api_route("/regression/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def regression_proxy(request: Request, path: str):
    return await _proxy(request, REGRESSION_URL, f"/{path}")


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    status = {"gateway": "healthy"}
    for name, base in [("classification", CLASSIFICATION_URL), ("regression", REGRESSION_URL)]:
        try:
            r = await _client.get(f"{base}/health", timeout=3.0)
            status[name] = "healthy" if r.status_code == 200 else "degraded"
        except Exception:
            status[name] = "unreachable"
    return status


@app.get("/")
async def root():
    return {
        "message": "Prometheus Gateway",
        "version": "2.0.0",
        "routes": {
            "classification": "/classification/...",
            "regression": "/regression/...",
            "health": "/health",
            "docs": "/docs",
        },
    }
