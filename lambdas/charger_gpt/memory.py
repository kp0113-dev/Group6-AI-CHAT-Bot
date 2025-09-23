import json
import time
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from . import config as cfg

DDB = boto3.resource("dynamodb")


def get_user_id(event: Dict[str, Any]) -> str:
    return (
        event.get("sessionId")
        or event.get("userId")
        or event.get("sessionState", {}).get("userId")
        or cfg.DEFAULT_STUDENT_ID
    )


def load_persistent_memory(user_id: str) -> Dict[str, str]:
    if not cfg.TABLE_CONVERSATIONS:
        return {}
    table = DDB.Table(cfg.TABLE_CONVERSATIONS)
    try:
        resp = table.get_item(Key={"user_id": user_id, "memory_key": "context"})
        item = resp.get("Item")
        if not item:
            return {}
        raw = item.get("data") or "{}"
        if isinstance(raw, str):
            return json.loads(raw)
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}

def save_persistent_memory(user_id: str, session_attrs: Dict[str, str]) -> None:
    if not cfg.TABLE_CONVERSATIONS:
        return
    table = DDB.Table(cfg.TABLE_CONVERSATIONS)
    try:
        table.put_item(
            Item={
                "user_id": user_id,
                "memory_key": "context",
                "data": json.dumps(session_attrs)[:35000],
            }
        )
    except Exception:
        pass


def append_turn_history(user_id: str, event: Dict[str, Any], response_message: str, session_attrs: Dict[str, str]) -> None:
    if not (cfg.FEATURE_CONVO_HISTORY and cfg.TABLE_CONVERSATIONS):
        return
    try:
        table = DDB.Table(cfg.TABLE_CONVERSATIONS)
        ts_ms = int(time.time() * 1000)
        expires_at = int(time.time()) + (cfg.CONVERSATIONS_TTL_DAYS * 86400)
        transcript = event.get("inputTranscript") or event.get("inputText") or ""
        intent = (
            event.get("sessionState", {}).get("intent", {}).get("name")
            or event.get("interpretations", [{}])[0].get("intent", {}).get("name")
            or ""
        )
        table.put_item(
            Item={
                "user_id": user_id,
                "memory_key": f"turn#{ts_ms}",
                "data": json.dumps(
                    {
                        "user": transcript,
                        "assistant": response_message,
                        "intent": intent,
                        "session_attrs": session_attrs,
                    }
                )[:35000],
                "expires_at": expires_at,
            }
        )
    except Exception:
        pass
