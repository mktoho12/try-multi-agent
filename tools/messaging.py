from __future__ import annotations

import json
import threading
import time
from collections import defaultdict

from tools.registry import ToolDef

_lock = threading.Lock()
_queues: dict[str, list[dict]] = defaultdict(list)


def send_message(to: str, subject: str, body: str, sender: str = "unknown") -> str:
    with _lock:
        _queues[to].append(
            {
                "from": sender,
                "subject": subject,
                "body": body,
                "timestamp": time.time(),
            }
        )
    return json.dumps({"status": "sent", "to": to})


def read_messages(recipient: str) -> str:
    with _lock:
        msgs = list(_queues.get(recipient, []))
    return json.dumps({"messages": msgs})


SEND_MESSAGE = ToolDef(
    name="send_message",
    description="Send a message to another agent via an in-memory queue.",
    input_schema={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient agent role name"},
            "subject": {"type": "string", "description": "Message subject"},
            "body": {"type": "string", "description": "Message body"},
            "sender": {"type": "string", "description": "Sender agent role name"},
        },
        "required": ["to", "subject", "body"],
    },
    handler=send_message,
)

READ_MESSAGES = ToolDef(
    name="read_messages",
    description="Read messages addressed to a given agent role.",
    input_schema={
        "type": "object",
        "properties": {
            "recipient": {"type": "string", "description": "Agent role name to read messages for"},
        },
        "required": ["recipient"],
    },
    handler=read_messages,
)
