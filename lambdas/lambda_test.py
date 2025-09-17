import json, os, logging, boto3
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

S3 = boto3.client("s3")
S3_BUCKET = os.getenv("S3_BUCKET_DATA")
S3_KEY = os.getenv("S3_BUILDINGS_KEY", "data/uah_buildings.json")

_CACHE: Dict[str, Any] = {}

# ---- Helpers for Lex ----
def _get_intent(event): 
    return event.get("sessionState", {}).get("intent", {}).get("name", "")

def _get_slots(event): 
    return event.get("sessionState", {}).get("intent", {}).get("slots", {}) or {}

def _get_slot(slots, name): 
    return (slots.get(name) or {}).get("value", {}).get("originalValue")

def _close(event, msg): 
    return {
        "sessionState": {
            **event["sessionState"],
            "dialogAction": {"type":"Close"},
            "intent": {**event["sessionState"].get("intent", {}), "state":"Fulfilled"},
        },
        "messages": [{"contentType":"PlainText","content": msg}],
    }

def _elicit(event, slot, prompt): 
    return {
        "sessionState": {
            **event["sessionState"],
            "dialogAction": {"type":"ElicitSlot","slotToElicit":slot},
            "intent": {**event["sessionState"].get("intent", {}), "state":"InProgress"},
        },
        "messages": [{"contentType":"PlainText","content": prompt}],
    }

# ---- Load building data ----
def _load_buildings() -> List[Dict[str, Any]]:
    if "buildings" in _CACHE:
        return _CACHE["buildings"]
    try:
        obj = S3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        data = json.loads(obj["Body"].read().decode("utf-8"))
        _CACHE["buildings"] = data
        return data
    except ClientError as e:
        logger.error("Could not load building data: %s", e)
        return []

def _normalize(s: str) -> str:
    return (s or "").strip().lower()

def _find_building(query: str) -> Optional[Dict[str, Any]]:
    q = _normalize(query)
    for b in _load_buildings():
        if q in (_normalize(b["building_id"]), _normalize(b["name"])):
            return b
    # fuzzy: substring
    for b in _load_buildings():
        if q in _normalize(b["name"]):
            return b
    return None

# ---- Intent handlers ----
def handle_hours(bname: str) -> str:
    b = _find_building(bname)
    if not b: return f"I couldn't find {bname}. Try the official name or code."
    hours = b.get("hours")
    if not hours:
        return f"{b['name']} hours are not listed. Address: {b['address']}."
    if isinstance(hours, dict) and "regular" in hours:
        return f"{b['name']} hours: {hours['regular']}. Address: {b['address']}."
    return f"{b['name']} hours: {hours}. Address: {b['address']}."

def handle_location(bname: str) -> str:
    b = _find_building(bname)
    if not b: return f"I couldn't find {bname}. Try again."
    return f"{b['name']} is at {b['address']}."

def handle_about(bname: str) -> str:
    b = _find_building(bname)
    if not b: return f"I couldn't find {bname}."
    hours = b.get("hours")
    if isinstance(hours, dict) and "regular" in hours:
        hours = "see schedule"
    return f"{b['name']} — {b['address']} — Hours: {hours or 'N/A'}"

# ---- Entry point ----
def lambda_handler(event, _ctx):
    intent = _get_intent(event)
    slots = _get_slots(event)
    transcript = event.get("inputTranscript","")

    if intent == "GetBuildingHoursIntent":
        b = _get_slot(slots,"BuildingName") or transcript
        return _elicit(event,"BuildingName","Which building?") if not b else _close(event, handle_hours(b))

    if intent == "GetCampusLocationIntent":
        b = _get_slot(slots,"BuildingName") or transcript
        return _elicit(event,"BuildingName","Which building?") if not b else _close(event, handle_location(b))

    if intent == "GetBuildingAboutIntent":
        b = _get_slot(slots,"BuildingName") or transcript
        return _elicit(event,"BuildingName","Which building?") if not b else _close(event, handle_about(b))

    return _close(event,"Ask about building hours, locations, or info.")
