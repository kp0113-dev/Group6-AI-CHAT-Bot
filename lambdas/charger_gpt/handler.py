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
    get_session_attrs,
)
from . import config as cfg
from .memory import (
    get_user_id as mem_get_user_id,
    load_persistent_memory as mem_load,
    save_persistent_memory as mem_save,
    append_turn_history as mem_append,
)
from .nlu import (
    infer_intent_from_rules as nlu_infer,
    looks_like_hours_query as nlu_looks_hours,
    looks_like_location_query as nlu_looks_location,
    looks_like_schedule_query as nlu_looks_schedule,
    looks_like_instructor_query as nlu_looks_instructor,
    resolve_building_reference as nlu_resolve_building,
    resolve_course_reference as nlu_resolve_course,
    resolve_pronoun_referent as nlu_resolve_referent,
    is_valid_course_code as nlu_is_valid_course,
)
from .data_access import find_building as da_find_building

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

DDB = boto3.resource("dynamodb")
S3 = boto3.client("s3")
BEDROCK = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))

TABLE_BUILDINGS = os.getenv("TABLE_BUILDINGS")
TABLE_SCHEDULES = os.getenv("TABLE_SCHEDULES")
TABLE_INSTRUCTORS = os.getenv("TABLE_INSTRUCTORS")
TABLE_CONVERSATIONS = os.getenv("TABLE_CONVERSATIONS")
S3_BUCKET_FAQS = os.getenv("S3_BUCKET_FAQS")
FEATURE_BEDROCK = os.getenv("FEATURE_BEDROCK", "false").lower() == "true"
DEFAULT_STUDENT_ID = os.getenv("DEFAULT_STUDENT_ID", "student123")
FEATURE_S3_DATA = os.getenv("FEATURE_S3_DATA", "false").lower() == "true"
S3_BUILDINGS_KEY = os.getenv("S3_BUILDINGS_KEY", "data/buildings.json")
S3_SCHEDULES_KEY = os.getenv("S3_SCHEDULES_KEY", "data/schedules.json")
S3_INSTRUCTORS_KEY = os.getenv("S3_INSTRUCTORS_KEY", "data/instructors.json")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "")
FEATURE_CONVO_HISTORY = os.getenv("FEATURE_CONVO_HISTORY", "true").lower() == "true"
S3_NLU_RULES_KEY = os.getenv("S3_NLU_RULES_KEY", "config/nlu_rules.json")
CONVERSATIONS_TTL_DAYS = int(os.getenv("CONVERSATIONS_TTL_DAYS", "30"))

# Cache FAQs on cold start
_FAQS_CACHE: Optional[Dict[str, Any]] = None
_DATA_CACHE: Dict[str, Any] = {}
_NLU_RULES: Optional[Dict[str, Any]] = None


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


PRONOUNS_BUILDING = {"it", "there", "that", "the building"}
PRONOUNS_COURSE = {"it", "that", "this", "the course", "the class"}


def _resolve_building_reference(candidate: Optional[str], transcript: str, session_attrs: Dict[str, str]) -> Optional[str]:
    return nlu_resolve_building(candidate, transcript, session_attrs)


def _normalize_course_code(text: Optional[str]) -> str:
    t = (text or "").strip().upper()
    # remove spaces and hyphens
    return t.replace(" ", "").replace("-", "")


def _resolve_course_reference(candidate: Optional[str], transcript: str, session_attrs: Dict[str, str]) -> Optional[str]:
    return nlu_resolve_course(candidate, transcript, session_attrs)


def _load_nlu_rules() -> Dict[str, Any]:
    global _NLU_RULES
    if _NLU_RULES is not None:
        return _NLU_RULES
    rules: Dict[str, Any] = {}
    try:
        cfg = _load_json_from_s3(S3_NLU_RULES_KEY)
        if isinstance(cfg, dict):
            rules = cfg
    except Exception as e:
        logger.debug("No NLU rules found in S3: %s", e)
    _NLU_RULES = rules
    return rules


def infer_intent_from_rules(text: str) -> Optional[str]:
    # Delegate to NLU module
    return nlu_infer(text)


def _append_turn_history(user_id: str, event: Dict[str, Any], response_message: str, session_attrs: Dict[str, str]) -> None:
    # Delegate to memory module (handles TTL and structure)
    mem_append(user_id, event, response_message, session_attrs)


def _looks_like_hours_query(text: str) -> bool:
    return nlu_looks_hours(text)


def _looks_like_location_query(text: str) -> bool:
    return nlu_looks_location(text)


def _looks_like_schedule_query(text: str) -> bool:
    return nlu_looks_schedule(text)


def _looks_like_instructor_query(text: str) -> bool:
    return nlu_looks_instructor(text)


def _extract_building_from_text(text: str) -> Optional[str]:
    t = _normalize(text)
    for item in get_buildings_data():
        name = item.get("name", "")
        if _is_building_match(name, t):
            return item.get("name")
    return None


def _get_user_id(event: Dict[str, Any]) -> str:
    # Delegate to memory module helper
    return mem_get_user_id(event)


def load_persistent_memory(user_id: str) -> Dict[str, str]:
    # Delegate to memory module
    return mem_load(user_id)


def save_persistent_memory(user_id: str, session_attrs: Dict[str, str]) -> None:
    # Delegate to memory module
    mem_save(user_id, session_attrs)


def _log_session(event: Dict[str, Any], action: str, session_attrs: Dict[str, str], extra: Optional[Dict[str, Any]] = None) -> None:
    try:
        payload = {
            "action": action,
            "intent": get_intent_name_v2(event),
            "session_attrs": session_attrs,
        }
        if extra:
            payload.update(extra)
        logger.info("session_state: %s", json.dumps(payload)[:8000])
    except Exception as e:
        logger.debug("_log_session failed: %s", e)


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


def find_building(building_query: str) -> Optional[dict]:
    # Delegate to data_access module
    return da_find_building(building_query)


def handle_building_hours(building_name: str) -> str:
    item = find_building(building_name)
    if item:
        hours = item.get("hours", "Hours not available")
        addr = item.get("address", "Address not available")
        return f"{item.get('name')} hours: {hours}. Address: {addr}."
    return "I couldn't find that building. Try asking 'What are the hours for the library?'"


def handle_building_location(building_name: str) -> str:
    item = find_building(building_name)
    if item:
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

    session_attrs = get_session_attrs(event)
    user_id = _get_user_id(event)
    # Merge persistent memory (DynamoDB) into current session attrs
    persisted = load_persistent_memory(user_id)
    if persisted:
        # Do not overwrite current session fields if already present in this turn
        merged = {**persisted, **session_attrs}
        session_attrs = merged

    # Pronoun-first routing: if the user likely refers to a previous subject, decide referent before intents
    tnorm = _normalize(transcript)
    if any(p in tnorm.split() for p in ("it", "that", "this")) or _looks_like_hours_query(tnorm) or _looks_like_location_query(tnorm) or _looks_like_schedule_query(tnorm) or _looks_like_instructor_query(tnorm):
        referent = nlu_resolve_referent(transcript, session_attrs)
        if referent == "building":
            # Prefer explicit building mentioned in this utterance; fallback to memory
            bname = _extract_building_from_text(transcript) or session_attrs.get("last_building_name")
            if bname:
                item = find_building(bname)
                if item:
                    # Prefer hours if explicitly asked, else location
                    if _looks_like_hours_query(transcript):
                        hours = item.get("hours", "Hours not available")
                        addr = item.get("address", "Address not available")
                        msg = f"{item.get('name')} hours: {hours}. Address: {addr}."
                        session_attrs.update({"last_building_name": item.get("name", ""), "last_intent": "GetBuildingHoursIntent"})
                        _log_session(event, "pronoun_first_hours", session_attrs, {"building": item.get("name")})
                        save_persistent_memory(user_id, session_attrs)
                        _append_turn_history(user_id, event, msg, session_attrs)
                        return close_intent(event, msg, session_attrs)
                    else:
                        addr = item.get("address", "Address not available")
                        lat = item.get("lat")
                        lon = item.get("lon")
                        if lat is not None and lon is not None:
                            msg = f"{item.get('name')} is at {addr} (lat: {lat}, lon: {lon})."
                        else:
                            msg = f"{item.get('name')} is at {addr}."
                        session_attrs.update({"last_building_name": item.get("name", ""), "last_intent": "GetCampusLocationIntent"})
                        _log_session(event, "pronoun_first_location", session_attrs, {"building": item.get("name")})
                        save_persistent_memory(user_id, session_attrs)
                        _append_turn_history(user_id, event, msg, session_attrs)
                        return close_intent(event, msg, session_attrs)
        elif referent == "course":
            lc = session_attrs.get("last_course_code")
            if lc:
                if _looks_like_schedule_query(transcript):
                    student_id = DEFAULT_STUDENT_ID
                    message = handle_class_schedule(student_id, lc)
                    _log_session(event, "pronoun_first_schedule", session_attrs, {"course_code": lc})
                    save_persistent_memory(user_id, session_attrs)
                    _append_turn_history(user_id, event, message, session_attrs)
                    return close_intent(event, message, session_attrs)
                if _looks_like_instructor_query(transcript):
                    message = handle_instructor_lookup(lc)
                    _log_session(event, "pronoun_first_instructor", session_attrs, {"course_code": lc})
                    save_persistent_memory(user_id, session_attrs)
                    _append_turn_history(user_id, event, message, session_attrs)
                    return close_intent(event, message, session_attrs)

    # Try rule-based inference for incomplete/ambiguous phrases
    inferred = infer_intent_from_rules(transcript)
    if inferred and (intent_name == "AMAZON.FallbackIntent" or intent_name not in {"GetBuildingHoursIntent","GetCampusLocationIntent","GetFAQIntent","GetClassScheduleIntent","GetInstructorLookupIntent"}):
        intent_name = inferred

    if intent_name == "GetBuildingHoursIntent":
        candidate = get_slot_value(slots, "BuildingName")
        # Try slot -> pronoun-memory -> extract from transcript -> fallback to whole transcript
        building_name = (
            _resolve_building_reference(candidate, transcript, session_attrs)
            or _extract_building_from_text(transcript)
            or candidate
            or transcript
        )
        if not building_name:
            return elicit_slot(event, "BuildingName", "Which building?", session_attrs)
        item = find_building(building_name)
        if item:
            session_attrs.update({
                "last_building_name": item.get("name", ""),
                "last_intent": intent_name,
            })
            hours = item.get("hours", "Hours not available")
            addr = item.get("address", "Address not available")
            msg = f"{item.get('name')} hours: {hours}. Address: {addr}."
            _log_session(event, "building_hours", session_attrs, {"building": item.get("name")})
            save_persistent_memory(user_id, session_attrs)
            _append_turn_history(user_id, event, msg, session_attrs)
            return close_intent(event, msg, session_attrs)
        _log_session(event, "building_hours_not_found", session_attrs, {"query": building_name})
        save_persistent_memory(user_id, session_attrs)
        _append_turn_history(user_id, event, "I couldn't find that building. Try asking 'What are the hours for the library?'", session_attrs)
        return close_intent(event, "I couldn't find that building. Try asking 'What are the hours for the library?'", session_attrs)

    if intent_name == "GetCampusLocationIntent":
        candidate = get_slot_value(slots, "BuildingName")
        # Try slot -> pronoun-memory -> extract from transcript -> fallback to whole transcript
        building_name = (
            _resolve_building_reference(candidate, transcript, session_attrs)
            or _extract_building_from_text(transcript)
            or candidate
            or transcript
        )
        if not building_name:
            return elicit_slot(event, "BuildingName", "Which building?", session_attrs)
        item = find_building(building_name)
        if item:
            session_attrs.update({
                "last_building_name": item.get("name", ""),
                "last_intent": intent_name,
            })
            addr = item.get("address", "Address not available")
            lat = item.get("lat")
            lon = item.get("lon")
            if lat is not None and lon is not None:
                msg = f"{item.get('name')} is at {addr} (lat: {lat}, lon: {lon})."
            else:
                msg = f"{item.get('name')} is at {addr}."
            return close_intent(event, msg, session_attrs)
        _log_session(event, "building_location_not_found", session_attrs, {"query": building_name})
        save_persistent_memory(user_id, session_attrs)
        _append_turn_history(user_id, event, "I couldn't find that building. Try 'Where is the engineering building?'", session_attrs)
        return close_intent(event, "I couldn't find that building. Try 'Where is the engineering building?'", session_attrs)

    if intent_name == "GetFAQIntent":
        topic = get_slot_value(slots, "FaqTopic")
        if not topic:
            return elicit_slot(event, "FaqTopic", "What topic would you like to ask about?", session_attrs)
        session_attrs.update({"last_intent": intent_name, "last_topic": topic})
        message = handle_faq(topic)
        _log_session(event, "faq", session_attrs, {"topic": topic})
        save_persistent_memory(user_id, session_attrs)
        _append_turn_history(user_id, event, message, session_attrs)
        return close_intent(event, message, session_attrs)

    if intent_name == "GetClassScheduleIntent":
        if os.getenv("FEATURE_SCHEDULES", "true").lower() != "true":
            _log_session(event, "schedules_disabled", session_attrs)
            save_persistent_memory(user_id, session_attrs)
            return close_intent(event, "Class schedule feature is currently disabled.", session_attrs)
        course_code = get_slot_value(slots, "CourseCode")
        # If CourseCode is a pronoun or invalid (e.g., "library"), treat as missing
        if course_code and _normalize(course_code) in PRONOUNS_COURSE:
            course_code = None
        elif course_code and not nlu_is_valid_course(course_code):
            course_code = None
        if not course_code:
            # If user said something like "When is it open?" and Lex misrouted here,
            # try to answer building hours using last_building_name memory.
            if _looks_like_hours_query(transcript) and session_attrs.get("last_building_name"):
                bname = session_attrs.get("last_building_name")
                item = find_building(bname)
                if item:
                    hours = item.get("hours", "Hours not available")
                    addr = item.get("address", "Address not available")
                    msg = f"{item.get('name')} hours: {hours}. Address: {addr}."
                    _log_session(event, "hours_reroute_from_schedule", session_attrs, {"building": item.get("name")})
                    save_persistent_memory(user_id, session_attrs)
                    _append_turn_history(user_id, event, msg, session_attrs)
                    return close_intent(event, msg, session_attrs)
            # If user said something like "Where is it?", reroute to location
            if _looks_like_location_query(transcript) and session_attrs.get("last_building_name"):
                bname = session_attrs.get("last_building_name")
                item = find_building(bname)
                if item:
                    addr = item.get("address", "Address not available")
                    lat = item.get("lat")
                    lon = item.get("lon")
                    if lat is not None and lon is not None:
                        msg = f"{item.get('name')} is at {addr} (lat: {lat}, lon: {lon})."
                    else:
                        msg = f"{item.get('name')} is at {addr}."
                    _log_session(event, "location_reroute_from_schedule", session_attrs, {"building": item.get("name")})
                    save_persistent_memory(user_id, session_attrs)
                    _append_turn_history(user_id, event, msg, session_attrs)
                    return close_intent(event, msg, session_attrs)
            return elicit_slot(event, "CourseCode", "Which course code? e.g., CS101", session_attrs)
        student_id = DEFAULT_STUDENT_ID
        message = handle_class_schedule(student_id, course_code)
        session_attrs.update({"last_intent": intent_name, "last_course_code": (course_code or "").upper()})
        _log_session(event, "class_schedule", session_attrs, {"course_code": (course_code or "").upper()})
        _append_turn_history(user_id, event, message, session_attrs)
        return close_intent(event, message, session_attrs)

    if intent_name == "GetInstructorLookupIntent":
        if os.getenv("FEATURE_INSTRUCTORS", "true").lower() != "true":
            _log_session(event, "instructors_disabled", session_attrs)
            save_persistent_memory(user_id, session_attrs)
            return close_intent(event, "Instructor lookup feature is currently disabled.", session_attrs)
        course_code = get_slot_value(slots, "CourseCode")
        # If CourseCode is a pronoun or invalid, treat as missing and elicit
        if course_code and _normalize(course_code) in PRONOUNS_COURSE:
            course_code = None
        elif course_code and not nlu_is_valid_course(course_code):
            course_code = None
        if not course_code:
            return elicit_slot(event, "CourseCode", "Which course code? e.g., ECE301", session_attrs)
        message = handle_instructor_lookup(course_code)
        session_attrs.update({"last_intent": intent_name, "last_course_code": (course_code or "").upper()})
        _log_session(event, "instructor_lookup", session_attrs, {"course_code": (course_code or "").upper()})
        _append_turn_history(user_id, event, message, session_attrs)
        return close_intent(event, message, session_attrs)

    # Fallback
    # Course follow-ups using remembered course when user asks generic questions
    if _looks_like_schedule_query(transcript) and session_attrs.get("last_course_code"):
        lc = session_attrs.get("last_course_code")
        student_id = DEFAULT_STUDENT_ID
        message = handle_class_schedule(student_id, lc)
        _log_session(event, "fallback_schedule", session_attrs, {"course_code": lc})
        save_persistent_memory(user_id, session_attrs)
        _append_turn_history(user_id, event, message, session_attrs)
        return close_intent(event, message, session_attrs)
    if _looks_like_instructor_query(transcript) and session_attrs.get("last_course_code"):
        lc = session_attrs.get("last_course_code")
        message = handle_instructor_lookup(lc)
        _log_session(event, "fallback_instructor", session_attrs, {"course_code": lc})
        save_persistent_memory(user_id, session_attrs)
        _append_turn_history(user_id, event, message, session_attrs)
        return close_intent(event, message, session_attrs)

    # If this looks like a location or hours query and we have a remembered building, answer it here.
    if _looks_like_location_query(transcript) and session_attrs.get("last_building_name"):
        bname = session_attrs.get("last_building_name")
        item = find_building(bname)
        if item:
            addr = item.get("address", "Address not available")
            lat = item.get("lat")
            lon = item.get("lon")
            if lat is not None and lon is not None:
                msg = f"{item.get('name')} is at {addr} (lat: {lat}, lon: {lon})."
            else:
                msg = f"{item.get('name')} is at {addr}."
            _log_session(event, "fallback_location", session_attrs, {"building": item.get("name")})
            save_persistent_memory(user_id, session_attrs)
            _append_turn_history(user_id, event, msg, session_attrs)
            return close_intent(event, msg, session_attrs)
    if _looks_like_hours_query(transcript) and session_attrs.get("last_building_name"):
        bname = session_attrs.get("last_building_name")
        item = find_building(bname)
        if item:
            hours = item.get("hours", "Hours not available")
            addr = item.get("address", "Address not available")
            msg = f"{item.get('name')} hours: {hours}. Address: {addr}."
            _log_session(event, "fallback_hours", session_attrs, {"building": item.get("name")})
            save_persistent_memory(user_id, session_attrs)
            _append_turn_history(user_id, event, msg, session_attrs)
            return close_intent(event, msg, session_attrs)

    _log_session(event, "fallback", session_attrs)
    save_persistent_memory(user_id, session_attrs)
    _append_turn_history(user_id, event, "Sorry, I didn't understand that. You can ask about building hours, locations, or FAQs.", session_attrs)
    return close_intent(event, "Sorry, I didn't understand that. You can ask about building hours, locations, or FAQs.", session_attrs)
