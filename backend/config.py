import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
E2B_API_KEY = os.getenv("E2B_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "llama3.1:8b")
OLLAMA_CODE_MODEL = os.getenv("OLLAMA_CODE_MODEL", "deepseek-coder:6.7b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///prometheus.db")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
E2B_TIMEOUT_SECONDS = int(os.getenv("E2B_TIMEOUT_SECONDS", "300"))
MAX_OPTUNA_TRIALS = int(os.getenv("MAX_OPTUNA_TRIALS", "20"))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_TASK_TYPES = {"binary_classification", "regression"}
ALLOWED_METRICS = {"roc_auc", "rmse", "mae", "r2"}
ALLOWED_MODEL_TYPES = {
    "LogisticRegression",
    "RandomForestClassifier",
    "GradientBoostingClassifier",
    "XGBClassifier",
    "LGBMClassifier",
    "Ridge",
    "RandomForestRegressor",
    "GradientBoostingRegressor",
    "XGBRegressor",
    "LGBMRegressor",
}
ALLOWED_IMPORTS = {
    "pandas", "numpy", "sklearn", "xgboost", "lightgbm",
    "scipy", "json", "sys", "os", "warnings",
    "sklearn.model_selection", "sklearn.preprocessing", "sklearn.linear_model",
    "sklearn.ensemble", "sklearn.metrics", "sklearn.pipeline", "sklearn.impute",
    "sklearn.compose", "sklearn.feature_selection",
}
