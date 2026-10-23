from typing import Any

from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
from langchain_core.messages import AIMessage, ToolMessage
from sentinel.core.domain import AuditStatus


class LangChainAuditMiddleware(AgentMiddleware):
    def wrap_model_call(self, request, handler):
        try:
            response = handler(request)
        except Exception as exc:
            request.runtime.context.audit.record_model_failure(exc)
            raise
        audit = request.runtime.context.audit
        messages = getattr(response, "result", [response])
        for message in messages:
            if isinstance(message, AIMessage):
                response_id = message.response_metadata.get("id")
                audit.record_model_response(response_id, message.usage_metadata)
        return response

    def wrap_tool_call(self, request: ToolCallRequest, handler) -> Any:
        details = {
            "call_id": request.tool_call.get("id"),
            "tool": request.tool_call.get("name"),
            "arguments": request.tool_call.get("args", {}),
        }
        try:
            result = handler(request)
        except Exception as exc:
            details.update({"status": AuditStatus.FAILED.value, "error": type(exc).__name__})
            request.runtime.context.audit.record("tool_call", details)
            raise
        if isinstance(result, ToolMessage):
            details.update({"output": result.content, "status": result.status})
        request.runtime.context.audit.record("tool_call", details)
        return result
