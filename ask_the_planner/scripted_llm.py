"""A fake model for tests: it runs a fixed SQL statement, then gives a fixed answer.

It lets the whole agent, tool and read only runner path be tested without an API key or any cost.
"""
from vanna.core.llm import LlmRequest, LlmResponse, LlmService, LlmStreamChunk
from vanna.core.tool import ToolCall


class ScriptedLlm(LlmService):
    def __init__(self, sql, final_text='Done.'):
        self.sql, self.final_text = sql, final_text
        self.system_prompts = []

    async def send_request(self, request: LlmRequest) -> LlmResponse:
        self.system_prompts.append(request.system_prompt)
        if any(m.role == 'tool' for m in request.messages):
            return LlmResponse(content=self.final_text, finish_reason='stop')
        call = ToolCall(id='call_1', name='run_sql', arguments={'sql': self.sql})
        return LlmResponse(content='', tool_calls=[call], finish_reason='tool_calls')

    async def stream_request(self, request: LlmRequest):
        response = await self.send_request(request)
        yield LlmStreamChunk(content=response.content, tool_calls=response.tool_calls, finish_reason=response.finish_reason)

    async def validate_tools(self, tools):
        return []
