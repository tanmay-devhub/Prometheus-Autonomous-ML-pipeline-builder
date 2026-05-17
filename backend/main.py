from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.jobs import router as jobs_router
from backend.routers.approvals import router as approvals_router

app = FastAPI(
    title="Prometheus",
    description="Autonomous ML Pipeline Builder",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(approvals_router)


@app.get("/")
async def root():
    return {"message": "Prometheus API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
