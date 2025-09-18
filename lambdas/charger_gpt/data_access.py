from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from . import config as cfg
from . import nlu

DDB = boto3.resource("dynamodb")
S3 = boto3.client("s3")


# --- Buildings ---

def get_buildings() -> List[Dict[str, Any]]:
    if cfg.FEATURE_S3_DATA:
        try:
            obj = S3.get_object(Bucket=cfg.S3_BUCKET_FAQS, Key=cfg.S3_BUILDINGS_KEY)
            data = obj["Body"].read().decode("utf-8")
            import json
            return json.loads(data) or []
        except ClientError:
            return []
    table = DDB.Table(cfg.TABLE_BUILDINGS)
    resp = table.scan()
    return resp.get("Items", [])


def find_building(building_query: str) -> Optional[Dict[str, Any]]:
    items = get_buildings()
    for item in items:
        if nlu.is_building_match(item.get("name", ""), building_query):
            return item
    return None


# --- Schedules ---

def get_schedule(student_id: str, course_code: str) -> Optional[Dict[str, Any]]:
    table = DDB.Table(cfg.TABLE_SCHEDULES)
    try:
        resp = table.get_item(Key={"student_id": student_id, "course_code": course_code.upper()})
        return resp.get("Item")
    except ClientError:
        return None


# --- Instructors ---

def get_instructor(course_code: str) -> Optional[Dict[str, Any]]:
    if cfg.FEATURE_S3_DATA:
        try:
            obj = S3.get_object(Bucket=cfg.S3_BUCKET_FAQS, Key=cfg.S3_INSTRUCTORS_KEY)
            import json
            data = json.loads(obj["Body"].read().decode("utf-8")) or []
            for it in data:
                if (it.get("course_code") or "").strip().upper() == course_code.strip().upper():
                    return it
            return None
        except ClientError:
            return None
    table = DDB.Table(cfg.TABLE_INSTRUCTORS)
    try:
        resp = table.get_item(Key={"course_code": course_code.upper()})
        return resp.get("Item")
    except ClientError:
        return None


# --- FAQs ---

def get_faqs() -> List[Dict[str, Any]]:
    try:
        obj = S3.get_object(Bucket=cfg.S3_BUCKET_FAQS, Key="faqs/faqs.json")
        import json
        return (json.loads(obj["Body"].read().decode("utf-8")) or {}).get("faqs", [])
    except ClientError:
        return []
