from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from classification.routers.jobs import router as cls_jobs_router
from classification.routers.approvals import router as cls_approvals_router
from regression.routers.jobs import router as reg_jobs_router
from regression.routers.approvals import router as reg_approvals_router
from multiclassification.routers.jobs import router as mc_jobs_router
from multiclassification.routers.approvals import router as mc_approvals_router
from timeseries.routers.jobs import router as ts_jobs_router
from timeseries.routers.approvals import router as ts_approvals_router
from auto.router import router as auto_router

app = FastAPI(
    title="Prometheus",
    description="Autonomous ML Pipeline Builder — classification, regression, multiclass classification, and time series forecasting",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cls_jobs_router, prefix="/classification")
app.include_router(cls_approvals_router, prefix="/classification")
app.include_router(reg_jobs_router, prefix="/regression")
app.include_router(reg_approvals_router, prefix="/regression")
app.include_router(mc_jobs_router, prefix="/multiclassification")
app.include_router(mc_approvals_router, prefix="/multiclassification")
app.include_router(ts_jobs_router, prefix="/timeseries")
app.include_router(ts_approvals_router, prefix="/timeseries")
app.include_router(auto_router)


@app.get("/")
async def root():
    return {
        "message": "Prometheus API",
        "version": "4.0.0",
        "docs": "/docs",
        "services": {
            "classification": "/classification/jobs",
            "regression": "/regression/jobs",
            "multiclassification": "/multiclassification/jobs",
            "timeseries": "/timeseries/jobs",
            "auto": "/auto/jobs",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
