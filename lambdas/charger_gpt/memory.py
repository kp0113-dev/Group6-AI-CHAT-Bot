import json
import time
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
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


def get_session_id(event: Dict[str, Any]) -> str:
    """Best-effort session identifier from Lex event.
    Falls back to user_id if sessionId is not present.
    """
    sid = (
        event.get("sessionId")
        or event.get("sessionState", {}).get("sessionId")
        or ""
    )
    return sid or get_user_id(event)


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
        # Exclude ephemeral, non-persistent keys
        filtered = {k: v for k, v in (session_attrs or {}).items() if k not in {"recent_context"}}
        table.put_item(
            Item={
                "user_id": user_id,
                "memory_key": "context",
                "data": json.dumps(filtered)[:35000],
            }
        )
    except Exception:
        pass

def append_turn_history(user_id: str, event: Dict[str, Any], response_message: str, session_attrs: Dict[str, str]) -> None:
    if not (cfg.FEATURE_CONVO_HISTORY and cfg.TABLE_CONVERSATIONS):
        return
    table = DDB.Table(cfg.TABLE_CONVERSATIONS)
    try:
        now_ms = int(time.time() * 1000)
        turn_id = f"turn#{now_ms}"
        session_id = get_session_id(event)
        # Prefix memory_key with session for easy Query by begins_with
        memory_key = f"session#{session_id}#{turn_id}"
        ttl = int(time.time()) + (cfg.CONVERSATIONS_TTL_DAYS * 24 * 60 * 60)
        table.put_item(
            Item={
                "user_id": user_id,
                "memory_key": memory_key,
                "expires_at": ttl,
                "data": {
                    "user_input": event.get("inputTranscript") or event.get("inputText"),
                    "assistant_response": response_message,
                    "intent": event.get("sessionState", {}).get("intent", {}).get("name"),
                    "slots": event.get("sessionState", {}).get("intent", {}).get("slots"),
                    "session_attrs": session_attrs,
                    "timestamp_ms": now_ms,
                    "session_id": session_id,
                },
            }
        )
    except Exception:
        pass


def get_recent_turns(user_id: str, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    if not (cfg.FEATURE_CONVO_HISTORY and cfg.TABLE_CONVERSATIONS):
        return []
    table = DDB.Table(cfg.TABLE_CONVERSATIONS)
    prefix = f"session#{session_id}#"
    try:
        resp = table.query(
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("memory_key").begins_with(prefix),
            ScanIndexForward=False,
            Limit=max(1, min(100, int(limit))),
        )
        return resp.get("Items", [])
    except Exception:
        return []
