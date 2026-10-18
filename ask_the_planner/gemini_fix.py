"""Fixes for Vanna 2.0.2's Gemini service so it works with current Gemini models.

Vanna is archived, and its Gemini code has three problems with today's API:
  1. it sends tool results with the role 'function', which the API now rejects (400 INVALID_ARGUMENT)
  2. it drops the thought signature that newer models attach to a tool call and expect back
  3. it gives every tool call the same id ('call_run_sql'), so two queries in one answer collide
This subclass keeps everything else from Vanna and only replaces how the conversation is sent and read.
"""
import asyncio
import json
import time
import uuid

from vanna.core.tool import ToolCall
from vanna.integrations.google import GeminiLlmService


class FixedGeminiLlmService(GeminiLlmService):
    min_interval = 0.0  # seconds between calls; the evaluation raises it to stay under per minute limits

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._calls = {}  # tool call id -> (function name, thought signature)
        self._last_call = 0.0

    async def send_request(self, request):
        wait = self._last_call + self.min_interval - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()
        return await super().send_request(request)

    def _parse_response(self, response):
        text_parts, tool_calls = [], []
        candidate = response.candidates[0] if response.candidates else None
        parts = getattr(getattr(candidate, 'content', None), 'parts', None) or []
        for part in parts:
            if getattr(part, 'text', None) and not getattr(part, 'thought', False):
                text_parts.append(part.text)
            call = getattr(part, 'function_call', None)
            if call:
                call_id = f'call_{call.name}_{uuid.uuid4().hex[:8]}'
                self._calls[call_id] = (call.name, getattr(part, 'thought_signature', None))
                tool_calls.append(ToolCall(id=call_id, name=call.name, arguments=dict(call.args or {})))
        return ''.join(text_parts), tool_calls

    def _build_payload(self, request):
        _, config = super()._build_payload(request)  # keep Vanna's tools and generation settings
        t = self._types
        contents = []
        for m in request.messages:
            if m.role == 'user':
                contents.append(t.Content(role='user', parts=[t.Part(text=m.content)]))
            elif m.role == 'assistant':
                parts = [t.Part(text=m.content)] if m.content and m.content.strip() else []
                for tc in m.tool_calls or []:
                    part = t.Part(function_call=t.FunctionCall(name=tc.name, args=tc.arguments))
                    signature = self._calls.get(tc.id, (None, None))[1]
                    if signature:
                        part.thought_signature = signature
                    parts.append(part)
                if parts:
                    contents.append(t.Content(role='model', parts=parts))
            elif m.role == 'tool' and m.tool_call_id:
                try:
                    payload = json.loads(m.content)
                except (json.JSONDecodeError, TypeError):
                    payload = {'result': m.content}
                if not isinstance(payload, dict):
                    payload = {'result': payload}
                name = self._calls.get(m.tool_call_id, (m.tool_call_id.replace('call_', ''), None))[0]
                contents.append(t.Content(role='user', parts=[t.Part(function_response=t.FunctionResponse(name=name, response=payload))]))
        return contents, config
