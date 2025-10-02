import json
import os
import time
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

# Environment variables expected:
# - TABLE_CONVERSATIONS (required): DynamoDB table name
# - FEATURE_CONVO_HISTORY (optional): "true" to enable history writes (default true)
# - CONVERSATIONS_TTL_DAYS (optional): integer days (default 30)
# - DEFAULT_STUDENT_ID (optional): fallback user id

DDB = boto3.resource("dynamodb")


def _table() -> Optional[Any]:
    name = os.getenv("TABLE_CONVERSATIONS")
    if not name:
        return None
    return DDB.Table(name)


def _feature_enabled() -> bool:
    return os.getenv("FEATURE_CONVO_HISTORY", "true").lower() == "true"


def _ttl_seconds() -> int:
    try:
        return int(os.getenv("CONVERSATIONS_TTL_DAYS", "30")) * 24 * 60 * 60
    except Exception:
        return 30 * 24 * 60 * 60


def get_user_id(event: Dict[str, Any]) -> str:
    return (
        event.get("sessionId")
        or event.get("userId")
        or event.get("sessionState", {}).get("userId")
        or os.getenv("DEFAULT_STUDENT_ID", "student123")
    )


def get_session_id(event: Dict[str, Any]) -> str:
    sid = (
        event.get("sessionId")
        or event.get("sessionState", {}).get("sessionId")
        or ""
    )
    return sid or get_user_id(event)


def load_persistent_memory(user_id: str) -> Dict[str, str]:
    tbl = _table()
    if not tbl:
        return {}
    try:
        resp = tbl.get_item(Key={"user_id": user_id, "memory_key": "context"})
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
    tbl = _table()
    if not tbl:
        return
    try:
        filtered = {k: v for k, v in (session_attrs or {}).items() if k not in {"recent_context"}}
        tbl.put_item(
            Item={
                "user_id": user_id,
                "memory_key": "context",
                "data": json.dumps(filtered)[:35000],
            }
        )
    except Exception:
        pass


def append_turn_history(user_id: str, event: Dict[str, Any], response_message: str, session_attrs: Dict[str, str]) -> None:
    if not _feature_enabled():
        return
    tbl = _table()
    if not tbl:
        return
    try:
        now_ms = int(time.time() * 1000)
        turn_id = f"turn#{now_ms}"
        session_id = get_session_id(event)
        memory_key = f"session#{session_id}#{turn_id}"
        ttl = int(time.time()) + _ttl_seconds()
        tbl.put_item(
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
    if not _feature_enabled():
        return []
    tbl = _table()
    if not tbl:
        return []
    prefix = f"session#{session_id}#"
    try:
        resp = tbl.query(
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("memory_key").begins_with(prefix),
            ScanIndexForward=False,
            Limit=max(1, min(100, int(limit))),
        )
        return resp.get("Items", [])
    except Exception:
        return []
