import json
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

S3 = boto3.client("s3")
S3_BUCKET_FAQS = None  # will be passed via env at deploy


def _load_faqs(bucket: str) -> Dict[str, Any]:
    try:
        obj = S3.get_object(Bucket=bucket, Key="faqs/faqs.json")
        body = obj["Body"].read().decode("utf-8")
        return json.loads(body) if body else {"faqs": []}
    except ClientError:
        return {"faqs": []}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    global S3_BUCKET_FAQS
    if S3_BUCKET_FAQS is None:
        import os
        S3_BUCKET_FAQS = os.getenv("S3_BUCKET_FAQS", "")
    topic = (event.get("topic") or "").strip()
    if not topic:
        return {"message": "What topic would you like to ask about?", "error": "missing_topic"}
    faqs = _load_faqs(S3_BUCKET_FAQS).get("faqs", [])
    tnorm = topic.lower().strip()
    for faq in faqs:
        q = (faq.get("question") or "").lower().strip()
        if tnorm in q or any(tnorm in (kw or "").lower() for kw in faq.get("keywords", [])):
            return {"message": faq.get("answer", "I don't have an answer yet."), "session_attrs": {"last_intent": "GetFAQIntent", "last_topic": topic}}
    return {"message": "I couldn't find that in my FAQs yet. Please try a different phrase or ask about buildings or hours.", "session_attrs": {"last_intent": "GetFAQIntent", "last_topic": topic}}
