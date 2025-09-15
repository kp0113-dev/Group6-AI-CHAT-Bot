import json
import logging
import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from .utils import (
    build_lex_message,
    close_intent,
    elicit_slot,
    get_slot_value,
    get_intent_name_v2,
    get_slots_v2,
)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

DDB = boto3.resource("dynamodb")
S3 = boto3.client("s3")
BEDROCK = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))

TABLE_BUILDINGS = os.getenv("TABLE_BUILDINGS")
TABLE_SCHEDULES = os.getenv("TABLE_SCHEDULES")
TABLE_INSTRUCTORS = os.getenv("TABLE_INSTRUCTORS")
S3_BUCKET_FAQS = os.getenv("S3_BUCKET_FAQS")
FEATURE_BEDROCK = os.getenv("FEATURE_BEDROCK", "false").lower() == "true"
DEFAULT_STUDENT_ID = os.getenv("DEFAULT_STUDENT_ID", "student123")
FEATURE_S3_DATA = os.getenv("FEATURE_S3_DATA", "false").lower() == "true"
S3_BUILDINGS_KEY = os.getenv("S3_BUILDINGS_KEY", "data/buildings.json")
S3_SCHEDULES_KEY = os.getenv("S3_SCHEDULES_KEY", "data/schedules.json")
S3_INSTRUCTORS_KEY = os.getenv("S3_INSTRUCTORS_KEY", "data/instructors.json")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "")

# Cache FAQs on cold start
_FAQS_CACHE: Optional[Dict[str, Any]] = None
_DATA_CACHE: Dict[str, Any] = {}


def _load_faqs() -> Dict[str, Any]:
    global _FAQS_CACHE
    if _FAQS_CACHE is not None:
        return _FAQS_CACHE
    try:
        obj = S3.get_object(Bucket=S3_BUCKET_FAQS, Key="faqs/faqs.json")
        body = obj["Body"].read().decode("utf-8")
        data = json.loads(body)
        _FAQS_CACHE = data
        return data
    except ClientError as e:
        logger.exception("Failed to load FAQs from S3: %s", e)
        return {"faqs": []}


def _normalize(text: Optional[str]) -> str:
    return (text or "").strip().lower()


def _normalize_building(text: Optional[str]) -> str:
    t = _normalize(text)
    # Remove leading articles
    for prefix in ("the ", "a ", "an "):
        if t.startswith(prefix):
            t = t[len(prefix):]
            break
    # Remove common suffixes
    for suffix in (" building", " hall"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
            break
    # Collapse multiple spaces
    t = " ".join(t.split())
    return t


def _is_building_match(item_name: str, query: str) -> bool:
    a = _normalize_building(item_name)
    b = _normalize_building(query)
    if not a or not b:
        return False
    if a == b:
        return True
    # Allow substring containment (e.g., 'library' vs 'm. louis salmon library')
    return a in b or b in a


def _load_json_from_s3(key: str) -> Any:
    try:
        obj = S3.get_object(Bucket=S3_BUCKET_FAQS, Key=key)
        body = obj["Body"].read().decode("utf-8")
        return json.loads(body)
    except ClientError as e:
        logger.error("Failed to load %s from S3 %s: %s", key, S3_BUCKET_FAQS, e)
        return None


def get_buildings_data() -> list:
    if FEATURE_S3_DATA:
        cache_key = "buildings"
        if cache_key not in _DATA_CACHE:
            data = _load_json_from_s3(S3_BUILDINGS_KEY) or []
            _DATA_CACHE[cache_key] = data
        return _DATA_CACHE.get(cache_key, [])
    # Fallback to DynamoDB
    table = DDB.Table(TABLE_BUILDINGS)
    resp = table.scan()
    return resp.get("Items", [])


def get_schedules_data(student_id: str) -> list:
    if FEATURE_S3_DATA:
        cache_key = f"schedules:{student_id}"
        if cache_key not in _DATA_CACHE:
            data = _load_json_from_s3(S3_SCHEDULES_KEY) or []
            # filter by student_id
            _DATA_CACHE[cache_key] = [x for x in data if _normalize(x.get("student_id")) == _normalize(student_id)]
        return _DATA_CACHE.get(cache_key, [])
    # DynamoDB
    table = DDB.Table(TABLE_SCHEDULES)
    # Using GetItem in original code; here allow simple scan for MVP if Query not available due to lack of GSI
    # But we can still get-item because PK/SK are known.
    # We'll query each course as needed, so return empty here.
    return []


def get_instructor_data(course_code: str) -> Optional[dict]:
    if FEATURE_S3_DATA:
        cache_key = "instructors"
        if cache_key not in _DATA_CACHE:
            data = _load_json_from_s3(S3_INSTRUCTORS_KEY) or []
            _DATA_CACHE[cache_key] = data
        for it in _DATA_CACHE.get(cache_key, []):
            if _normalize(it.get("course_code")) == _normalize(course_code):
                return it
        return None
    # DynamoDB
    table = DDB.Table(TABLE_INSTRUCTORS)
    try:
        resp = table.get_item(Key={"course_code": course_code.upper()})
        return resp.get("Item")
    except ClientError as e:
        logger.exception("DynamoDB error: %s", e)
        return None


def _invoke_bedrock(prompt: str) -> Optional[str]:
    if not (FEATURE_BEDROCK and BEDROCK_MODEL_ID):
        return None
    model = BEDROCK_MODEL_ID
    try:
        if model.startswith("anthropic."):
            payload = {
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": prompt}]}
                ],
                "max_tokens": 300,
                "temperature": 0.2,
            }
            resp = BEDROCK.invoke_model(modelId=model, body=json.dumps(payload))
            body = json.loads(resp["body"].read())
            # Claude messages format
            content = body.get("content", [])
            if content and isinstance(content, list):
                for block in content:
                    if block.get("type") == "text":
                        return block.get("text")
            return None
        else:
            # Titan or other models (generic text)
            payload = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 300,
                    "temperature": 0.2,
                },
            }
            resp = BEDROCK.invoke_model(modelId=model, body=json.dumps(payload))
            body = json.loads(resp["body"].read())
            return body.get("results", [{}])[0].get("outputText")
    except Exception as e:
        logger.exception("Bedrock invoke failed: %s", e)
        return None


def handle_building_hours(building_name: str) -> str:
    items = get_buildings_data()
    for item in items:
        if _is_building_match(item.get("name", ""), building_name):
            hours = item.get("hours", "Hours not available")
            addr = item.get("address", "Address not available")
            return f"{item.get('name')} hours: {hours}. Address: {addr}."

    return "I couldn't find that building. Try asking 'What are the hours for the library?'"


def handle_building_location(building_name: str) -> str:
    items = get_buildings_data()
    for item in items:
        if _is_building_match(item.get("name", ""), building_name):
            addr = item.get("address", "Address not available")
            lat = item.get("lat")
            lon = item.get("lon")
            if lat is not None and lon is not None:
                return f"{item.get('name')} is at {addr} (lat: {lat}, lon: {lon})."
            return f"{item.get('name')} is at {addr}."

    return "I couldn't find that building. Try 'Where is the engineering building?'"


def handle_faq(topic: str) -> str:
    faqs = _load_faqs().get("faqs", [])
    tnorm = _normalize(topic)
    # simple keyword search
    for faq in faqs:
        q = _normalize(faq.get("question"))
        if tnorm in q or any(tnorm in _normalize(k) for k in faq.get("keywords", [])):
            return faq.get("answer", "I don't have an answer yet.")

    # Fallback if Bedrock is enabled later
    if FEATURE_BEDROCK and BEDROCK_MODEL_ID:
        # Provide some lightweight context from known FAQs
        examples = "\n".join([f"Q: {f.get('question')}\nA: {f.get('answer')}" for f in faqs[:3]])
        prompt = (
            "You are ChargerGPT, a helpful assistant for The University of Alabama in Huntsville (UAH).\n"
            "Answer concisely based on campus context. If unsure, say you don't know.\n\n"
            f"User question: {topic}\n\n"
            f"Relevant examples (may be helpful, but not exhaustive):\n{examples}\n"
        )
        gen = _invoke_bedrock(prompt)
        if gen:
            return gen.strip()
        return "I couldn't find that in my FAQs yet. Please try a different phrase or ask about buildings or hours."

    return (
        "I couldn't find that in my FAQs yet. Please try a different phrase or ask about buildings or hours."
    )


def handle_class_schedule(student_id: str, course_code: str) -> str:
    table = DDB.Table(TABLE_SCHEDULES)
    try:
        resp = table.get_item(Key={"student_id": student_id, "course_code": course_code.upper()})
        item = resp.get("Item")
        if not item:
            return "I couldn't find that class in your schedule."
        location = item.get("location", "TBD")
        time = item.get("time", "TBD")
        building = item.get("building", "")
        return f"{course_code.upper()} meets at {time} in {building} ({location})."
    except ClientError as e:
        logger.exception("DynamoDB error: %s", e)
        return "There was a problem looking up your schedule. Please try again."


def handle_instructor_lookup(course_code: str) -> str:
    item = get_instructor_data(course_code)
    if not item:
        return "I couldn't find the instructor for that course."
    name = item.get("instructor_name", "Unknown")
    email = item.get("email", "")
    office = item.get("office", "")
    parts = [f"{course_code.upper()} is taught by {name}"]
    if email:
        parts.append(f"(email: {email})")
    if office:
        parts.append(f"office: {office}")
    return ", ".join(parts) + "."


# Lex V2 event router

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    logger.debug("Event: %s", json.dumps(event))

    intent_name = get_intent_name_v2(event)
    slots = get_slots_v2(event)
    # Attempt to infer missing BuildingName from transcript for robustness (best-effort)
    transcript = event.get("inputTranscript") or event.get("inputText") or ""

    if intent_name == "GetBuildingHoursIntent":
        building_name = get_slot_value(slots, "BuildingName") or transcript
        if not building_name:
            return elicit_slot(event, "BuildingName", "Which building?")
        message = handle_building_hours(building_name)
        return close_intent(event, message)

    if intent_name == "GetCampusLocationIntent":
        building_name = get_slot_value(slots, "BuildingName") or transcript
        if not building_name:
            return elicit_slot(event, "BuildingName", "Which building?")
        message = handle_building_location(building_name)
        return close_intent(event, message)

    if intent_name == "GetFAQIntent":
        topic = get_slot_value(slots, "FaqTopic")
        if not topic:
            return elicit_slot(event, "FaqTopic", "What topic would you like to ask about?")
        message = handle_faq(topic)
        return close_intent(event, message)

    if intent_name == "GetClassScheduleIntent":
        if os.getenv("FEATURE_SCHEDULES", "true").lower() != "true":
            return close_intent(event, "Class schedule feature is currently disabled.")
        course_code = get_slot_value(slots, "CourseCode")
        if not course_code:
            return elicit_slot(event, "CourseCode", "Which course code? e.g., CS101")
        student_id = DEFAULT_STUDENT_ID
        message = handle_class_schedule(student_id, course_code)
        return close_intent(event, message)

    if intent_name == "GetInstructorLookupIntent":
        if os.getenv("FEATURE_INSTRUCTORS", "true").lower() != "true":
            return close_intent(event, "Instructor lookup feature is currently disabled.")
        course_code = get_slot_value(slots, "CourseCode")
        if not course_code:
            return elicit_slot(event, "CourseCode", "Which course code? e.g., ECE301")
        message = handle_instructor_lookup(course_code)
        return close_intent(event, message)

    # Fallback
    return close_intent(event, "Sorry, I didn't understand that. You can ask about building hours, locations, or FAQs.")
