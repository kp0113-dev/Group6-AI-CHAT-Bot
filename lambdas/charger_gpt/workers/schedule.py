import os
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

TABLE_SCHEDULES = os.getenv("TABLE_SCHEDULES")
DDB = boto3.resource("dynamodb")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    student_id = (event.get("student_id") or "").strip()
    course_code = (event.get("course_code") or "").strip().upper()
    if not student_id or not course_code:
        return {"message": "Missing student_id or course_code.", "error": "missing_params"}
    table = DDB.Table(TABLE_SCHEDULES)
    try:
        resp = table.get_item(Key={"student_id": student_id, "course_code": course_code})
        item = resp.get("Item")
        if not item:
            return {"message": "I couldn't find that class in your schedule.", "error": "not_found"}
        location = item.get("location", "TBD")
        time = item.get("time", "TBD")
        building = item.get("building", "")
        msg = f"{course_code} meets at {time} in {building} ({location})."
        return {
            "message": msg,
            "session_attrs": {
                "last_course_code": course_code,
                "last_intent": "GetClassScheduleIntent",
            },
            "course_code": course_code,
        }
    except ClientError:
        return {"message": "There was a problem looking up your schedule. Please try again.", "error": "ddb_error"}
