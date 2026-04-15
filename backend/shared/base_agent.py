import httpx
import time
from typing import Optional
import json
import os
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

load_dotenv()

# Import centralized logger
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.logger import logger


class AgentException(Exception):
    def __init__(self, agent: str, error: str):
        self.agent = agent
        self.error = error
        super().__init__(f"{agent} failed: {error}")


class BaseAgent:
    
    def __init__(self, agent_name: str):
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.agent_name = agent_name
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _call_llm(self, prompt: str, max_tokens: int = 1000, trace_name: Optional[str] = None) -> str:
        start_time = time.monotonic()
        trace_label = trace_name or "unnamed"
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()["response"]
                
                latency_ms = round((time.monotonic() - start_time) * 1000)
                
                logger.info(
                    "LLM call completed",
                    agent=self.agent_name,
                    trace=trace_label,
                    model=self.ollama_model,
                    prompt_len=len(prompt),
                    response_len=len(result),
                    latency_ms=latency_ms,
                    max_tokens=max_tokens,
                )
                return result
            
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            # Let tenacity handle these retryable errors
            raise
        except Exception as e:
            latency_ms = round((time.monotonic() - start_time) * 1000)
            logger.error(
                "LLM call failed (non-retryable)",
                agent=self.agent_name,
                trace=trace_label,
                error=str(e),
                latency_ms=latency_ms,
            )
            raise AgentException(agent=self.agent_name, error=str(e))
    
    def _parse_json(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start == -1 or end == 0:
                logger.warning(
                    "No JSON found in LLM response",
                    agent=self.agent_name,
                    response_preview=response[:200],
                )
                raise ValueError(f"No JSON found in response: {response}")
            return json.loads(response[start:end])