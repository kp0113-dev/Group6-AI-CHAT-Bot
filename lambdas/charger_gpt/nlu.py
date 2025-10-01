import json
from typing import Any, Dict, Optional
import re

import boto3
from botocore.exceptions import ClientError

from . import config as cfg

S3 = boto3.client("s3")

# --- Normalization helpers ---

def normalize(text: Optional[str]) -> str:
    return (text or "").strip().lower()


def normalize_building(text: Optional[str]) -> str:
    t = normalize(text)
    for prefix in ("the ", "a ", "an "):
        if t.startswith(prefix):
            t = t[len(prefix) :]
            break
    for suffix in (" building", " hall"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
            break
    return " ".join(t.split())


def is_building_match(item_name: str, query: str) -> bool:
    a = normalize_building(item_name)
    b = normalize_building(query)
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a


PRONOUNS_BUILDING = {"it", "there", "that", "the building"}
PRONOUNS_COURSE = {"it", "that", "this", "the course", "the class"}


def normalize_course_code(text: Optional[str]) -> str:
    t = (text or "").strip().upper()
    return t.replace(" ", "").replace("-", "")


def resolve_building_reference(candidate: Optional[str], transcript: str, session_attrs: Dict[str, str]) -> Optional[str]:
    cand = (candidate or "").strip()
    if cand:
        if normalize(cand) in PRONOUNS_BUILDING:
            remembered = session_attrs.get("last_building_name")
            return remembered or cand
        return cand
    t = normalize(transcript)
    if any(p in t.split() for p in PRONOUNS_BUILDING):
        remembered = session_attrs.get("last_building_name")
        if remembered:
            return remembered
    return cand or None


def resolve_course_reference(candidate: Optional[str], transcript: str, session_attrs: Dict[str, str]) -> Optional[str]:
    cand = (candidate or "").strip()
    if cand:
        if normalize(cand) in PRONOUNS_COURSE:
            remembered = session_attrs.get("last_course_code")
            return remembered or cand
        return normalize_course_code(cand)
    t = normalize(transcript)
    if any(p in t.split() for p in PRONOUNS_COURSE):
        remembered = session_attrs.get("last_course_code")
        if remembered:
            return remembered
    return None


# --- Query heuristics ---

def looks_like_hours_query(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ("hours", "open", "opening", "close", "closing"))


def looks_like_location_query(text: str) -> bool:
    t = normalize(text)
    return t.startswith("where is") or t.startswith("where's") or ("location" in t)


def looks_like_schedule_query(text: str) -> bool:
    t = normalize(text)
    return ((t.startswith("when is") or t.startswith("what time")) and ("class" in t or "it" in t or "schedule" in t)) or (
        "schedule" in t and ("for" in t or "of" in t)
    )


def looks_like_instructor_query(text: str) -> bool:
    t = normalize(text)
    return ("who teaches" in t) or ("instructor" in t) or ("professor" in t) or ("teacher" in t)


# --- NLU rules loading and inference ---
_rules_cache: Optional[Dict[str, Any]] = None


def _load_rules_from_s3() -> Dict[str, Any]:
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    rules: Dict[str, Any] = {}
    if not (cfg.S3_BUCKET_FAQS and cfg.S3_NLU_RULES_KEY):
        _rules_cache = rules
        return rules
    try:
        obj = S3.get_object(Bucket=cfg.S3_BUCKET_FAQS, Key=cfg.S3_NLU_RULES_KEY)
        data = obj["Body"].read().decode("utf-8")
        rules = json.loads(data) if data else {}
    except ClientError:
        rules = {}
    _rules_cache = rules
    return rules


def infer_intent_from_rules(text: str) -> Optional[str]:
    t = normalize(text)
    rules = _load_rules_from_s3()
    try:
        for rule in rules.get("rules", []):
            kws = [k.lower() for k in rule.get("keywords", [])]
            if kws and all(k in t for k in kws):
                return rule.get("intent")
    except Exception:
        pass
    # Allow "where is" anywhere in the utterance (handles noise/prefixes)
    if ("where is" in t) or ("where's" in t) or t.startswith("where is the"):
        return "GetCampusLocationIntent"
    if looks_like_hours_query(t):
        return "GetBuildingHoursIntent"
    # Simple FAQ mapping for common topics
    faq_keywords = ("parking", "dining", "tuition", "admissions", "financial aid", "scholarship")
    if any(k in t for k in faq_keywords):
        return "GetFAQIntent"
    return None


# --- Additional helpers for pronoun-first routing ---

_COURSE_CODE_RE = re.compile(r"^[A-Za-z]{2,5}\s?-?\d{3}[A-Za-z]?$")


def is_valid_course_code(text: Optional[str]) -> bool:
    if not text:
        return False
    t = (text or "").strip()
    # Accept common patterns like CS101, ECE-301, MATH 201
    return bool(_COURSE_CODE_RE.match(t))


def resolve_pronoun_referent(transcript: str, session_attrs: Dict[str, str]) -> Optional[str]:
    """Decide if a pronoun like 'it' refers to a building or a course.
    Heuristics:
    - If looks like hours/location: prefer building (when memory exists).
    - If looks like schedule/instructor: prefer course (when memory exists).
    - Otherwise, prefer the last_intent's domain (building vs course) if available.
    Returns: 'building', 'course', or None.
    """
    t = normalize(transcript)
    has_building = bool(session_attrs.get("last_building_name"))
    has_course = bool(session_attrs.get("last_course_code"))

    # Strong signals from the current utterance
    if looks_like_hours_query(t) or looks_like_location_query(t):
        if has_building:
            return "building"
    if looks_like_schedule_query(t) or looks_like_instructor_query(t):
        if has_course:
            return "course"

    # Fall back to last intent domain
    last_intent = (session_attrs.get("last_intent") or "").strip()
    if last_intent in {"GetBuildingHoursIntent", "GetCampusLocationIntent"} and has_building:
        return "building"
    if last_intent in {"GetClassScheduleIntent", "GetInstructorLookupIntent"} and has_course:
        return "course"

    return None
