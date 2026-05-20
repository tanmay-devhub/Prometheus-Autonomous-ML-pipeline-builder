from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from classification.routers.jobs import router as jobs_router
from classification.routers.approvals import router as approvals_router

app = FastAPI(
    title="Prometheus Classification Service",
    description="Binary classification ML pipeline microservice",
    version="2.0.0",
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
    return {"message": "Classification Service", "version": "2.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "classification"}
