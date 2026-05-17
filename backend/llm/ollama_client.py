import asyncio
from typing import List
import ollama
from ollama import AsyncClient


class OllamaUnavailableError(Exception):
    pass


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.client = AsyncClient(host=base_url)

    async def chat(self, model: str, messages: List[dict], temperature: float = 0.1) -> str:
        last_error = None
        for attempt in range(3):
            try:
                response = await self.client.chat(
                    model=model,
                    messages=messages,
                    options={"temperature": temperature},
                )
                return response.message.content
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if "connection" in error_str or "refused" in error_str or "unavailable" in error_str:
                    if attempt < 2:
                        await asyncio.sleep(2)
                    continue
                raise

        raise OllamaUnavailableError(
            f"Ollama is not running or unreachable at {self.base_url}. "
            f"Start it with: ollama serve. Last error: {last_error}"
        )
