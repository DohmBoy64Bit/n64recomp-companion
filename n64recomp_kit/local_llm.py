"""Compatibility facade for the local LLM/MCP workflow.

Implementation is separated across transport, model API, policy/orchestration,
diagnostics, and generated-file modules.
"""
from .local_agent import (
    ToolPolicy,
    authorize_tool,
    classify_tool,
    local_llm_ask,
)
from .local_llm_diagnostics import format_local_llm_doctor, local_llm_doctor
from .local_llm_templates import (
    DEFAULT_MCP_SERVER_NAME,
    LocalLlmWorkflowReport,
    emit_local_llm_workflow,
)
from .mcp_stdio import McpStdioClient
from .openai_compat import (
    DEFAULT_LLAMA_CPP_BASE_URL,
    DEFAULT_LMSTUDIO_BASE_URL,
    first_assistant_message,
    openai_tools_from_mcp,
    probe_openai_compatible,
    probe_tool_call_capability,
)

_openai_tools_from_mcp = openai_tools_from_mcp

__all__ = [
    "DEFAULT_LLAMA_CPP_BASE_URL",
    "DEFAULT_LMSTUDIO_BASE_URL",
    "DEFAULT_MCP_SERVER_NAME",
    "LocalLlmWorkflowReport",
    "McpStdioClient",
    "ToolPolicy",
    "authorize_tool",
    "classify_tool",
    "emit_local_llm_workflow",
    "first_assistant_message",
    "format_local_llm_doctor",
    "local_llm_ask",
    "local_llm_doctor",
    "openai_tools_from_mcp",
    "probe_openai_compatible",
    "probe_tool_call_capability",
]
