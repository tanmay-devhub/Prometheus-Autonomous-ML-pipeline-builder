import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("TIMESERIES_DB_URL", os.getenv("DATABASE_URL", "sqlite:///timeseries.db"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
E2B_TIMEOUT_SECONDS = int(os.getenv("E2B_TIMEOUT_SECONDS", "300"))

UPLOAD_DIR = "uploads/timeseries"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ARTIFACTS_DIR = "artifacts/timeseries"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

ALLOWED_TASK_TYPES = {"timeseries"}
ALLOWED_METRICS = {"rmse", "mae", "mape"}
ALLOWED_MODEL_TYPES = {
    "XGBRegressor",
    "LGBMRegressor",
    "RandomForestRegressor",
    "LinearRegression",
    "Ridge",
}
ALLOWED_IMPORTS = {
    "pandas", "numpy", "sklearn", "xgboost", "lightgbm",
    "scipy", "json", "sys", "os", "warnings", "re", "statsmodels",
}
