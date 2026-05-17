import asyncio
from datetime import date
from typing import List

import google.genai as genai
from google.genai import types as genai_types
from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.orm import declarative_base, Session

from backend.config import GEMINI_API_KEY, GEMINI_MODEL, DATABASE_URL

# Ordered list of model names to try — first working one wins
_MODEL_CANDIDATES = [
    GEMINI_MODEL,
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-001",
]
# Deduplicate while preserving order
_MODEL_CANDIDATES = list(dict.fromkeys(_MODEL_CANDIDATES))

Base = declarative_base()
DAILY_TOKEN_WARN_THRESHOLD = 900_000


class GeminiTokenUsage(Base):
    __tablename__ = "gemini_token_usage"
    id = Column(Integer, primary_key=True)
    usage_date = Column(Date, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)


class GeminiClient:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model_name = GEMINI_MODEL
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(self.engine)

    def _get_or_create_usage(self, session: Session) -> GeminiTokenUsage:
        today = date.today()
        usage = session.query(GeminiTokenUsage).filter_by(usage_date=today).first()
        if not usage:
            usage = GeminiTokenUsage(usage_date=today, input_tokens=0, output_tokens=0)
            session.add(usage)
            session.commit()
        return usage

    def _check_token_limit(self):
        with Session(self.engine) as session:
            usage = self._get_or_create_usage(session)
            total = (usage.input_tokens or 0) + (usage.output_tokens or 0)
            if total >= DAILY_TOKEN_WARN_THRESHOLD:
                print(
                    f"[WARNING] Gemini daily token usage ({total:,}) is approaching the free tier limit."
                )

    def _record_usage(self, input_tokens: int, output_tokens: int):
        with Session(self.engine) as session:
            usage = self._get_or_create_usage(session)
            usage.input_tokens = (usage.input_tokens or 0) + input_tokens
            usage.output_tokens = (usage.output_tokens or 0) + output_tokens
            session.commit()

    async def chat(self, messages: List[dict], temperature: float = 0.2) -> str:
        self._check_token_limit()

        system_text = ""
        user_text = ""
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            elif msg["role"] == "user":
                user_text = msg["content"]

        prompt = f"{system_text}\n\n{user_text}".strip() if system_text else user_text

        last_error = None
        for model_name in _MODEL_CANDIDATES:
            for attempt in range(2):
                try:
                    response = await asyncio.get_running_loop().run_in_executor(
                        None,
                        lambda m=model_name: self.client.models.generate_content(
                            model=m,
                            contents=prompt,
                            config=genai_types.GenerateContentConfig(temperature=temperature),
                        ),
                    )
                    self.model_name = model_name  # remember which one worked
                    try:
                        usage = response.usage_metadata
                        self._record_usage(
                            usage.prompt_token_count or 0,
                            usage.candidates_token_count or 0,
                        )
                    except Exception:
                        pass
                    return response.text
                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    if "404" in error_str or "not_found" in error_str or "not found" in error_str:
                        break  # this model name doesn't exist → try next candidate
                    if "rate" in error_str or "quota" in error_str or "429" in error_str:
                        if attempt < 1:
                            await asyncio.sleep(5)
                        continue
                    raise  # unexpected error → propagate immediately

        raise RuntimeError(f"Gemini API failed after retries: {last_error}")
