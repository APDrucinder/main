import asyncio

from shared.base_agent import BaseAgent

__test__ = False


class TestAgent(BaseAgent):
    def __init__(self):
        super().__init__("test_agent")

    async def run(self):
        response = await self._call_llm(
            prompt="Say hello in one word",
            max_tokens=10,
            trace_name="test_hello",
        )
        return response


async def main():
    agent = TestAgent()
    result = await agent.run()
    print(f"Agent response: {result}")


if __name__ == "__main__":
    asyncio.run(main())
