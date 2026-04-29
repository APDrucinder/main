from __future__ import annotations
import json
import os
import time
from typing import Optional
import httpx
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from shared.logger import logger

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()


class AgentException(Exception):
    def __init__(self, agent: str, error: str):
        self.agent = agent
        self.error = error
        super().__init__(f"{agent} failed: {error}")


class BaseAgent:

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.provider = LLM_PROVIDER

        if self.provider == "gemini":
            from google import genai
            # The client automatically picks up GEMINI_API_KEY from the environment
            self.gemini_client = genai.Client(
                api_key=os.getenv("GEMINI_API_KEY")
            )
            self.gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

        elif self.provider == "anthropic":
            import anthropic
            self.anthropic_client = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
            self.anthropic_model = os.getenv(
                "ANTHROPIC_MODEL", 
                "claude-haiku-4-5-20251001"
            )

        else:  # ollama
            self.ollama_url = os.getenv(
                "OLLAMA_URL", "http://localhost:11434"
            )
            self.ollama_model = os.getenv(
                "OLLAMA_MODEL", "llama3.2"
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _call_llm(
        self,
        prompt: str,
        max_tokens: int = 1000,
        trace_name: Optional[str] = None,
    ) -> str:

        start_time = time.monotonic()
        trace_label = trace_name or "unnamed"

        try:
            if self.provider == "gemini":
                result = await self._call_gemini(
                    prompt, max_tokens
                )

            elif self.provider == "anthropic":
                result = await self._call_anthropic(
                    prompt, max_tokens
                )

            else:
                result = await self._call_ollama(
                    prompt, max_tokens
                )

            latency_ms = round(
                (time.monotonic() - start_time) * 1000
            )
            logger.info(
                "LLM call completed",
                agent=self.agent_name,
                trace=trace_label,
                provider=self.provider,
                prompt_len=len(prompt),
                response_len=len(result),
                latency_ms=latency_ms,
            )
            return result

        except Exception as exc:
            latency_ms = round(
                (time.monotonic() - start_time) * 1000
            )
            logger.error(
                "LLM call failed",
                agent=self.agent_name,
                trace=trace_label,
                error=str(exc),
                latency_ms=latency_ms,
            )
            raise AgentException(
                agent=self.agent_name, 
                error=str(exc)
            )

    async def _call_gemini(
        self, prompt: str, max_tokens: int
    ) -> str:
        from google import genai
        
        # Using the new SDK's native async generation method
        response = await self.gemini_client.aio.models.generate_content(
            model=self.gemini_model_name,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.1,
            )
        )
        return response.text

    async def _call_anthropic(
        self, prompt: str, max_tokens: int
    ) -> str:
        import asyncio
        response = await asyncio.to_thread(
            self.anthropic_client.messages.create,
            model=self.anthropic_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    async def _call_ollama(
        self, prompt: str, max_tokens: int
    ) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")

    def _parse_json(self, response: str) -> dict:
        response = response.strip()
        if response.startswith("```"):
            response = response.strip("`")
            if response.lower().startswith("json"):
                response = response[4:].strip()
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end <= start:
                logger.warning(
                    "No JSON found in LLM response",
                    agent=self.agent_name,
                    response_preview=response[:200],
                )
                raise ValueError(
                    f"No JSON found in response: {response}"
                )
            return json.loads(response[start:end])