"""Tests for the tool registry and safe execution."""

import pytest

from app.tools.base import Tool
from app.tools.registry import ALL_TOOLS, SAFE_TOOLS, get_tool, openai_schemas


def test_catalog_sizes():
    assert len(ALL_TOOLS) == 9
    assert len(SAFE_TOOLS) == 6


def test_calculator_tool():
    tool = get_tool("calculator")
    result = tool.run({"expr": "8 * (2.5 + 1)"})
    assert "28.0" in result


def test_calculator_rejects_arbitrary_code():
    tool = get_tool("calculator")
    with pytest.raises(Exception):
        tool.run({"expr": "__import__('os').system('echo pwned')"})


def test_unknown_tool_raises():
    with pytest.raises(KeyError):
        get_tool("does_not_exist")


def test_needs_approval_flags():
    assert get_tool("send_email").needs_approval is True
    assert get_tool("run_python").needs_approval is True
    assert get_tool("web_search").needs_approval is False


def test_openai_schemas_shape():
    schemas = openai_schemas(["web_search"])
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "web_search"
    assert "parameters" in schemas[0]["function"]