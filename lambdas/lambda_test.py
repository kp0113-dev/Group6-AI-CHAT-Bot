import json, os, logging, boto3
from typing import Any, Dict, List, Optional
from botocore.exceptions import ClientError

# ---------- config / logging ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

S3_BUCKET = os.getenv("S3_BUCKET_DATA", "")
S3_KEY    = os.getenv("S3_BUILDINGS_KEY", "data/uah_buildings.json")
S3 = boto3.client("s3")

_CACHE: Dict[str, Any] = {}  # cold-start cache

# ---------- tiny Lex helpers (no external utils) ----------
def _intent_name(event: Dict[str, Any]) -> str:
    return (event.get("sessionState", {}).get("intent", {}) or {}).get("name", "")

def _slots(event: Dict[str, Any]) -> Dict[str, Any]:
    return (event.get("sessionState", {}).get("intent", {}) or {}).get("slots", {}) or {}

def _slot_value(slots: Dict[str, Any], slot_name: str) -> Optional[str]:
    v = (slots.get(slot_name) or {}).get("value", {}).get("originalValue")
    return v.strip() if isinstance(v, str) else None

def _close(event: Dict[str, Any], message: str) -> Dict[str, Any]:
    return {
        "sessionState": {
            **event.get("sessionState", {}),
            "dialogAction": {"type": "Close"},
            "intent": {**(event.get("sessionState", {}).get("intent", {}) or {}), "state": "Fulfilled"},
        },
        "messages": [{"contentType": "PlainText", "content": message}],
    }

def _elicit(event: Dict[str, Any], slot_name: str, prompt: str) -> Dict[str, Any]:
    return {
        "sessionState": {
            **event.get("sessionState", {}),
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_name},
            "intent": {**(event.get("sessionState", {}).get("intent", {}) or {}), "state": "InProgress"},
        },
        "messages": [{"contentType": "PlainText", "content": prompt}],
    }

# ---------- data load ----------
def _load_buildings() -> List[Dict[str, Any]]:
    if "buildings" in _CACHE:
        return _CACHE["buildings"]
    try:
        obj = S3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        data = json.loads(obj["Body"].read().decode("utf-8"))
        # Expecting a list of { building_id, name, address, hours?, lat?, lon?, aliases? }
        _CACHE["buildings"] = data
        logger.info("Loaded %d buildings from s3://%s/%s", len(data), S3_BUCKET, S3_KEY)
        return data
    except ClientError as e:
        logger.exception("Failed to load buildings JSON from S3")
        _CACHE["buildings"] = []
        return []

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _norm_building_text(s: Optional[str]) -> str:
    t = _norm(s)
    for pre in ("the ", "a ", "an "):
        if t.startswith(pre):
            t = t[len(pre):]
            break
    for suf in (" building", " hall"):
        if t.endswith(suf):
            t = t[: -len(suf)]
            break
    return " ".join(t.split())

def _is_match(item_name: str, query: str) -> bool:
    a = _norm_building_text(item_name)
    b = _norm_building_text(query)
    return bool(a and b) and (a == b or a in b or b in a)

def _find_building(q: str) -> Optional[Dict[str, Any]]:
    q_raw = q.strip()
    q_norm = _norm_building_text(q_raw)
    if not q_norm:
        return None

    items = _load_buildings()

    # 1) exact code match (e.g., CGU, ENG)
    for b in items:
        bid = str(b.get("building_id", ""))
        if bid and bid.upper() == q_raw.upper():
            return b

    # 2) alias match (if list exists)
    for b in items:
        aliases = b.get("aliases") or b.get("alt_names") or []
        for a in aliases if isinstance(aliases, list) else [aliases]:
            if _is_match(str(a), q_norm):
                return b

    # 3) name match / substring
    for b in items:
        if _is_match(str(b.get("name","")), q_norm):
            return b

    return None

# ---------- formatters ----------
def _fmt_hours(b: Dict[str, Any]) -> str:
    hours = b.get("hours")
    # supports either string or {"regular": "..."} style
    if isinstance(hours, dict) and "regular" in hours:
        hours_str = hours["regular"]
    else:
        hours_str = hours or "Hours not listed"
    addr = b.get("address") or "(address not listed)"
    return f"{b.get('name','(Unknown)')} hours: {hours_str}. Address: {addr}."

def _fmt_location(b: Dict[str, Any]) -> str:
    addr = b.get("address") or "(address not listed)"
    lat, lon = b.get("lat"), b.get("lon")
    if lat is not None and lon is not None:
        return f"{b.get('name','(Unknown)')} is at {addr} (lat: {lat}, lon: {lon})."
    return f"{b.get('name','(Unknown)')} is at {addr}."

def _fmt_about(b: Dict[str, Any]) -> str:
    hours = b.get("hours")
    if isinstance(hours, dict) and "regular" in hours:
        hours = hours["regular"]
    return f"{b.get('name','(Unknown)')} — {b.get('address','(address not listed)')} — Hours: {hours or 'N/A'}"

# ---------- handlers ----------
def _handle_hours(bname: str) -> str:
    b = _find_building(bname)
    return _fmt_hours(b) if b else f"I couldn't find '{bname}'. Try the official name or code (e.g., CGU, ENG)."

def _handle_location(bname: str) -> str:
    b = _find_building(bname)
    return _fmt_location(b) if b else f"I couldn't find '{bname}'. Try the official name or code."

def _handle_about(bname: str) -> str:
    b = _find_building(bname)
    return _fmt_about(b) if b else f"I couldn't find '{bname}'. Try the official name or code."

# ---------- entrypoint ----------
def lambda_handler(event: Dict[str, Any], _ctx: Any) -> Dict[str, Any]:
    intent = _intent_name(event)
    slots  = _slots(event)
    transcript = event.get("inputTranscript") or event.get("text") or ""

    if intent == "GetBuildingHoursIntent":
        b = _slot_value(slots, "BuildingName") or transcript
        return _elicit(event, "BuildingName", "Which building?") if not b else _close(event, _handle_hours(b))

    if intent == "GetCampusLocationIntent":
        b = _slot_value(slots, "BuildingName") or transcript
        return _elicit(event, "BuildingName", "Which building?") if not b else _close(event, _handle_location(b))

    if intent == "GetBuildingAboutIntent":
        b = _slot_value(slots, "BuildingName") or transcript
        return _elicit(event, "BuildingName", "Which building?") if not b else _close(event, _handle_about(b))

    # simple fallback: route by keywords
    t = transcript.lower()
    if any(k in t for k in ["hour", "open", "close"]):
        return _close(event, _handle_hours(transcript))
    if any(k in t for k in ["where", "address", "location"]):
        return _close(event, _handle_location(transcript))
    return _close(event, "Ask about building hours or location (e.g., 'hours for Charger Union', 'where is ENG').")
