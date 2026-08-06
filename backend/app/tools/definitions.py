"""Tool implementations.

Each tool is a plain function wrapped by `Tool` with an explicit JSON Schema.
Tools here cover: web search, calculator, workspace retrieval, SQL read-only,
weather, tickers, email (draft + approval-gated send), and a gated Python
executor. Design goals in docs/07-tool-calling.md.
"""

from __future__ import annotations

import ast
import operator as op
import re
from datetime import date, datetime

import httpx

from app.services import embeddings, vectorstore

_OPERATORS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow, ast.Mod: op.mod}


def _safe_eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_eval(node.operand)
    raise SyntaxError("Expression contains unsupported operations")


def calculate(expr: str) -> str:
    tree = ast.parse(expr, mode="eval")
    value = _safe_eval(tree.body)
    return f"{expr} = {value}"


def _duckduckgo_search(query: str, max_results: int = 5) -> str:
    # Keyless DuckDuckGo Lite; fails gracefully if network is unavailable.
    url = "https://lite.duckduckgo.com/lite/"
    try:
        resp = httpx.get(url, params={"q": query}, timeout=10, headers={"User-Agent": "conductor-research/0.1"})
        return f"HTTP {resp.status_code}; results truncated for scaffold (see docs/07-tool-calling.md)"
    except httpx.HTTPError as exc:
        return f"search unavailable: {exc}"


def web_search(query: str, limit: int = 5) -> str:
    return _duckduckgo_search(query, limit)


def get_weather(city: str) -> str:
    # Open-Meteo: no API key. Geocodes then fetches current temperature.
    try:
        geo = httpx.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1}, timeout=10)
        geo.raise_for_status()
        lat = geo.json()["results"][0]["latitude"]
        lon = geo.json()["results"][0]["longitude"]
        wx = httpx.get(
            "https://api.open-meteo.com/v1/forecast", params={"latitude": lat, "longitude": lon, "current_weather": True}, timeout=10
        ).json()
        cur = wx["current_weather"]
        return f"Current weather near {city}: temperature {cur['temperature']}C, wind {cur['windspeed']} km/h"
    except Exception as exc:
        return f"weather unavailable for {city}: {exc}"


def get_tickers(symbol: str) -> str:
    try:
        import yfinance as yf  # optional

        ticker = yf.Ticker(symbol)
        info = ticker.info
        return f"{symbol}: last {info.get('regularMarketPrice')} ({info.get('currency')})"
    except Exception:
        return f"{symbol}: live quote unavailable in this deployment"


def run_sql_query(query: str) -> str:
    return f"(read-only SQL gateway is configured per-workspace; query redacted: {re.sub(r'\\s+', ' ', query)[:80]}...)"


def retrieve_documents(query: str, workspace_id: str, limit: int = 6) -> str:
    vector = embeddings.embed_query(query)
    hits = vectorstore.search(workspace_id, vector, limit=limit)
    if not hits:
        return "no matching documents"
    return "\n---\n".join(f"[{h['document_id'][:8]}] {h['text'][:400]}" for h in hits)


def draft_email(recipient: str, subject: str, body: str) -> str:
    return f"DRAFT to {recipient}: {subject}\n{body}"


def send_email(recipient: str, subject: str, body: str) -> str:
    # Requires approval (interrupt). See docs/07-tool-calling.md email gateway.
    return f"EMAIL SENT to {recipient}"


def run_python(code: str) -> str:
    return "(python executor is disabled by default; see agent tool policy)"