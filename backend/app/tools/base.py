"""Tool primitive: schema, executor, permission flags.

`needs_approval=True` means execution halts on an interrupt until a human
grants it (used for email send, SQL writes, arbitrary code, etc.).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

import jsonschema


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema subset
    func: Callable[..., Any] = field(repr=False)
    needs_approval: bool = False
    read_only: bool = True

    def openai_schema(self) -> dict[str, object]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }

    def run(self, args: dict[str, Any]) -> str:
        """Validate args against the schema, execute, and stringify the result."""
        jsonschema.validate(instance=args, schema={"type": "object", "properties": self.parameters})
        result = self.func(**args)
        return str(result)

    @property
    def signature_hint(self) -> str:
        return f"{self.name}{inspect.signature(self.func)}"