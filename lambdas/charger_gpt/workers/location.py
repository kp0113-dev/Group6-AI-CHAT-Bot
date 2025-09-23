import json
from typing import Any, Dict

from .. import data_access as da


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    building_name = (event.get("building_name") or "").strip()
    if not building_name:
        return {"message": "Which building?", "error": "missing_building"}
    item = da.find_building(building_name)
    if not item:
        return {"message": "I couldn't find that building.", "error": "not_found"}
    addr = item.get("address", "Address not available")
    lat = item.get("lat")
    lon = item.get("lon")
    if lat is not None and lon is not None:
        msg = f"{item.get('name')} is at {addr} (lat: {lat}, lon: {lon})."
    else:
        msg = f"{item.get('name')} is at {addr}."
    return {
        "message": msg,
        "session_attrs": {
            "last_building_name": item.get("name", ""),
            "last_intent": "GetCampusLocationIntent",
        },
        "building": item.get("name"),
    }
