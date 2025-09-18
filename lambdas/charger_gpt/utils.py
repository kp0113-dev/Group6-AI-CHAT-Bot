import copy
from typing import Any, Dict, Optional


def get_intent_name_v2(event: Dict[str, Any]) -> str:
    return event.get("sessionState", {}).get("intent", {}).get("name", "")


def get_slots_v2(event: Dict[str, Any]) -> Dict[str, Any]:
    return event.get("sessionState", {}).get("intent", {}).get("slots", {}) or {}


def get_slot_value(slots: Dict[str, Any], name: str) -> Optional[str]:
    slot = slots.get(name)
    if not slot:
        return None
    value = slot.get("value") or {}
    return value.get("interpretedValue") or value.get("originalValue")


def build_lex_message(content: str) -> Dict[str, Any]:
    return {
        "contentType": "PlainText",
        "content": content,
    }


def _base_response(event: Dict[str, Any]) -> Dict[str, Any]:
    # Preserve session state
    session_state = copy.deepcopy(event.get("sessionState", {}))
    # Ensure dialogAction exists
    session_state.setdefault("dialogAction", {})
    return {
        "sessionState": session_state,
    }


def get_session_attrs(event: Dict[str, Any]) -> Dict[str, str]:
    return copy.deepcopy(event.get("sessionState", {}).get("sessionAttributes", {}) or {})


def _merge_session_attrs(resp: Dict[str, Any], new_attrs: Optional[Dict[str, str]]) -> None:
    if new_attrs is None:
        return
    current = resp.get("sessionState", {}).get("sessionAttributes", {}) or {}
    merged = {**current, **new_attrs}
    resp["sessionState"]["sessionAttributes"] = merged


def close_intent(event: Dict[str, Any], message: str, session_attrs: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    resp = _base_response(event)
    resp["sessionState"]["intent"] = resp["sessionState"].get("intent", {})
    resp["sessionState"]["intent"]["state"] = "Fulfilled"
    resp["messages"] = [build_lex_message(message)]
    resp["sessionState"]["dialogAction"] = {"type": "Close"}
    _merge_session_attrs(resp, session_attrs)
    return resp


def elicit_slot(event: Dict[str, Any], slot_to_elicit: str, prompt: str, session_attrs: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    resp = _base_response(event)
    resp["sessionState"]["intent"] = resp["sessionState"].get("intent", {})
    resp["sessionState"]["dialogAction"] = {
        "type": "ElicitSlot",
        "slotToElicit": slot_to_elicit,
    }
    resp["messages"] = [build_lex_message(prompt)]
    _merge_session_attrs(resp, session_attrs)
    return resp
