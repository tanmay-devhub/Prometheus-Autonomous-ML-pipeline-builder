import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
E2B_API_KEY = os.getenv("E2B_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "llama3.1:8b")
OLLAMA_CODE_MODEL = os.getenv("OLLAMA_CODE_MODEL", "deepseek-coder:6.7b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///prometheus.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
E2B_TIMEOUT_SECONDS = int(os.getenv("E2B_TIMEOUT_SECONDS", "300"))
