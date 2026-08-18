"""Stdio MCP (NDJSON, same framing as grok-orbit)."""

from __future__ import annotations

import json
import sys

from cell import __version__
from cell.actions import call, doctor, inbox, numbers, send_sms, status
from cell.models import NeedConfirm, ProviderError

PROTOCOL = "2024-11-05"

TOOLS = {
    "cell_status": {
        "description": "Show the Grok cell number, provider, balance, and owned numbers.",
        "schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "run": lambda _a: status(),
    },
    "cell_doctor": {
        "description": "Diagnose cell config and provider credentials (secrets masked).",
        "schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "run": lambda _a: doctor(),
    },
    "cell_numbers": {
        "description": "List PSTN numbers owned on the configured telephony provider.",
        "schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "run": lambda _a: numbers(),
    },
    "cell_inbox": {
        "description": "List recent SMS (inbound and outbound). Optional peer number filter.",
        "schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                "with": {"type": "string", "description": "Peer E.164 or US 10-digit number"},
            },
            "additionalProperties": False,
        },
        "run": lambda a: inbox(limit=int(a.get("limit") or 20), with_n=a.get("with")),
    },
    "cell_send": {
        "description": "Send an SMS from the owned number. Requires confirm=true. Costs money.",
        "schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "body": {"type": "string"},
                "confirm": {"type": "boolean", "description": "Must be true. Agent should only set this after the operator asked to send."},
            },
            "required": ["to", "body", "confirm"],
            "additionalProperties": False,
        },
        "run": lambda a: send_sms(str(a.get("to") or ""), str(a.get("body") or ""), yes=bool(a.get("confirm"))),
    },
    "cell_call": {
        "description": "Place an outbound voice call that speaks text. Requires confirm=true. Costs money.",
        "schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "say": {"type": "string"},
                "confirm": {"type": "boolean"},
            },
            "required": ["to", "confirm"],
            "additionalProperties": False,
        },
        "run": lambda a: call(str(a.get("to") or ""), say=a.get("say"), yes=bool(a.get("confirm"))),
    },
}


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}
    if method == "initialize":
        return _ok(
            mid,
            {
                "protocolVersion": params.get("protocolVersion") or PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "cell", "version": __version__},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _ok(mid, {})
    if method == "tools/list":
        tools = [
            {"name": name, "description": spec["description"], "inputSchema": spec["schema"]}
            for name, spec in TOOLS.items()
        ]
        return _ok(mid, {"tools": tools})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        spec = TOOLS.get(name)
        if not spec:
            return _err(mid, -32601, f"unknown tool {name}")
        try:
            payload = spec["run"](args)
            return _ok(mid, {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=True)}], "isError": False})
        except NeedConfirm as e:
            return _ok(
                mid,
                {"content": [{"type": "text", "text": f"needs confirm: {e}"}], "isError": True},
            )
        except (ProviderError, ValueError) as e:
            return _ok(
                mid,
                {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True},
            )
        except Exception as e:
            return _ok(
                mid,
                {"content": [{"type": "text", "text": f"error: {type(e).__name__}: {e}"}], "isError": True},
            )
    if mid is not None:
        return _err(mid, -32601, f"Method not found: {method}")
    return None


def _ok(id_, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0
