import time
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import declarative_base, Session

from backend.config import (
    OLLAMA_BASE_URL, OLLAMA_REASONING_MODEL, OLLAMA_CODE_MODEL,
    GEMINI_MODEL, DATABASE_URL,
)
from backend.llm.ollama_client import OllamaClient
from backend.llm.gemini_client import GeminiClient

Base = declarative_base()

OLLAMA_TASKS = {"code_generation", "code_fix", "reasoning", "analysis", "interpretation"}
GEMINI_TASKS = {"complex_decision", "ensemble_decision", "fix_vs_pivot"}

CODE_TASKS = {"code_generation", "code_fix"}
REASONING_TASKS = {"reasoning", "analysis", "interpretation"}


class LLMCallLog(Base):
    __tablename__ = "llm_call_log"
    id = Column(Integer, primary_key=True)
    task_type = Column(String)
    model_used = Column(String)
    input_tokens_estimate = Column(Integer)
    output_tokens_estimate = Column(Integer)
    latency_ms = Column(Float)
    success = Column(Boolean)


class LLMRouter:
    def __init__(self):
        self.ollama = OllamaClient(base_url=OLLAMA_BASE_URL)
        self.gemini = GeminiClient()
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(self.engine)

    def _select_model(self, task_type: str) -> tuple[str, str]:
        """Returns (backend, model_name)."""
        if task_type in CODE_TASKS:
            return "ollama", OLLAMA_CODE_MODEL
        if task_type in REASONING_TASKS:
            return "ollama", OLLAMA_REASONING_MODEL
        if task_type in GEMINI_TASKS:
            return "gemini", GEMINI_MODEL
        raise ValueError(f"Unknown task_type: {task_type}")

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _log_call(self, task_type: str, model: str, input_text: str, output_text: str, latency_ms: float, success: bool):
        with Session(self.engine) as session:
            log = LLMCallLog(
                task_type=task_type,
                model_used=model,
                input_tokens_estimate=self._estimate_tokens(input_text),
                output_tokens_estimate=self._estimate_tokens(output_text),
                latency_ms=latency_ms,
                success=success,
            )
            session.add(log)
            session.commit()

    async def call(
        self,
        task_type: str,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
    ) -> str:
        backend, model_name = self._select_model(task_type)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        if temperature is None:
            temperature = 0.1 if task_type in CODE_TASKS else 0.3

        start = time.time()
        success = False
        result = ""
        actual_model = model_name
        try:
            if backend == "ollama":
                result = await self.ollama.chat(model=model_name, messages=messages, temperature=temperature)
            else:
                try:
                    result = await self.gemini.chat(messages=messages, temperature=temperature)
                except Exception as gemini_err:
                    # Fall back to Ollama reasoning model so pipeline never dies on Gemini issues
                    print(f"[LLMRouter] Gemini failed ({gemini_err}), falling back to Ollama {OLLAMA_REASONING_MODEL}")
                    actual_model = OLLAMA_REASONING_MODEL
                    result = await self.ollama.chat(
                        model=OLLAMA_REASONING_MODEL, messages=messages, temperature=temperature
                    )
            success = True
            return result
        finally:
            latency_ms = (time.time() - start) * 1000
            self._log_call(
                task_type=task_type,
                model=actual_model,
                input_text=system_prompt + user_message,
                output_text=result,
                latency_ms=latency_ms,
                success=success,
            )
