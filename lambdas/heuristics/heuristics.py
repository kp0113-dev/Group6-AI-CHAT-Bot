# Map of intents that allow reusing the last subject
REUSE_LAST_SUBJECT = {
    "BuildingInfo-GetTime": True,
    "BuildingInfo-GetLocation": True,
    "ProfessorInfo-GetProfessorInfo": True,
    "GetMap": True,
}

def can_reuse_subject(intent_name: str) -> bool:
    """
    Returns True if this intent is allowed to reuse the last subject.
    """
    return REUSE_LAST_SUBJECT.get(intent_name, False)
