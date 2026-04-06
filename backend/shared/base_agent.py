import requests
from typing import Optional
import json
import os
from dotenv import load_dotenv

load_dotenv()

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
    
    async def _call_llm(self, prompt: str, max_tokens: int = 1000, trace_name: Optional[str] = None) -> str:
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()["response"]
            print(f"[{self.agent_name}] LLM response received ({len(result)} chars)")
            return result
            
        except Exception as e:
            raise AgentException(agent=self.agent_name, error=str(e))
    
    def _parse_json(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError(f"No JSON found in response: {response}")
            return json.loads(response[start:end])