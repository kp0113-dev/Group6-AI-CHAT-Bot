import json
import re
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

S3 = boto3.client("s3")
S3_BUCKET_FAQS = None  # will be passed via env at deploy


def _load_faqs(bucket: str) -> Dict[str, Any]:
    try:
        obj = S3.get_object(Bucket=bucket, Key="faqs/faqs.json")
        raw = obj["Body"].read()
        # Use utf-8-sig to handle potential BOM
        text = raw.decode("utf-8-sig", errors="ignore")
        try:
            return json.loads(text) if text else {"faqs": []}
        except json.JSONDecodeError:
            # Try without BOM logic as a fallback
            text2 = raw.decode("utf-8", errors="ignore")
            return json.loads(text2) if text2 else {"faqs": []}
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
    # Normalize: keep alphanumerics and spaces only
    tnorm = re.sub(r"[^a-z0-9 ]+", " ", topic.lower()).strip()
    for faq in faqs:
        q_raw = (faq.get("question") or "")
        qnorm = re.sub(r"[^a-z0-9 ]+", " ", q_raw.lower()).strip()
        keywords = [str(kw or "").lower().strip() for kw in faq.get("keywords", [])]
        # Match if user's normalized text is contained in question OR contains any keyword
        if (tnorm and tnorm in qnorm) or any((kw and kw in tnorm) for kw in keywords):
            return {
                "message": faq.get("answer", "I don't have an answer yet."),
                "session_attrs": {"last_intent": "GetFAQIntent", "last_topic": topic},
            }
    return {"message": "I couldn't find that in my FAQs yet. Please try a different phrase or ask about buildings or hours.", "session_attrs": {"last_intent": "GetFAQIntent", "last_topic": topic}}
