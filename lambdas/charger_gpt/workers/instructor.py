import os
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

TABLE_INSTRUCTORS = os.getenv("TABLE_INSTRUCTORS")
DDB = boto3.resource("dynamodb")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    course_code = (event.get("course_code") or "").strip().upper()
    if not course_code:
        return {"message": "Which course code? e.g., ECE301", "error": "missing_course"}
    table = DDB.Table(TABLE_INSTRUCTORS)
    try:
        resp = table.get_item(Key={"course_code": course_code})
        item = resp.get("Item")
        if not item:
            return {"message": "I couldn't find the instructor for that course.", "error": "not_found"}
        name = item.get("instructor_name", "Unknown")
        email = item.get("email", "")
        office = item.get("office", "")
        parts = [f"{course_code} is taught by {name}"]
        if email:
            parts.append(f"(email: {email})")
        if office:
            parts.append(f"office: {office}")
        msg = ", ".join(parts) + "."
        return {
            "message": msg,
            "session_attrs": {
                "last_course_code": course_code,
                "last_intent": "GetInstructorLookupIntent",
            },
            "course_code": course_code,
        }
    except ClientError:
        return {"message": "There was a problem looking up the instructor. Please try again.", "error": "ddb_error"}
