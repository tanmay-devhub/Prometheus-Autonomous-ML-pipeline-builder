import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("REGRESSION_DB_URL", os.getenv("DATABASE_URL", "sqlite:///regression.db"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
E2B_TIMEOUT_SECONDS = int(os.getenv("E2B_TIMEOUT_SECONDS", "300"))

UPLOAD_DIR = "uploads/regression"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ARTIFACTS_DIR = "artifacts/regression"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

ALLOWED_TASK_TYPES = {"regression"}
ALLOWED_METRICS = {"rmse", "mae", "r2"}
ALLOWED_MODEL_TYPES = {
    "Ridge",
    "Lasso",
    "RandomForestRegressor",
    "GradientBoostingRegressor",
    "XGBRegressor",
    "LGBMRegressor",
}
ALLOWED_IMPORTS = {
    "pandas", "numpy", "sklearn", "xgboost", "lightgbm",
    "scipy", "json", "sys", "os", "warnings", "re",
}
