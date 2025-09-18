import os
from typing import Optional

# Global configuration and feature flags
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
FEATURE_BEDROCK = os.getenv("FEATURE_BEDROCK", "false").lower() == "true"
DEFAULT_STUDENT_ID = os.getenv("DEFAULT_STUDENT_ID", "student123")
FEATURE_S3_DATA = os.getenv("FEATURE_S3_DATA", "false").lower() == "true"
S3_BUILDINGS_KEY = os.getenv("S3_BUILDINGS_KEY", "data/buildings.json")
S3_SCHEDULES_KEY = os.getenv("S3_SCHEDULES_KEY", "data/schedules.json")
S3_INSTRUCTORS_KEY = os.getenv("S3_INSTRUCTORS_KEY", "data/instructors.json")
FEATURE_CONVO_HISTORY = os.getenv("FEATURE_CONVO_HISTORY", "true").lower() == "true"
S3_NLU_RULES_KEY = os.getenv("S3_NLU_RULES_KEY", "config/nlu_rules.json")
CONVERSATIONS_TTL_DAYS = int(os.getenv("CONVERSATIONS_TTL_DAYS", "30"))

# Resource names
TABLE_BUILDINGS = os.getenv("TABLE_BUILDINGS")
TABLE_SCHEDULES = os.getenv("TABLE_SCHEDULES")
TABLE_INSTRUCTORS = os.getenv("TABLE_INSTRUCTORS")
TABLE_CONVERSATIONS = os.getenv("TABLE_CONVERSATIONS")
S3_BUCKET_FAQS = os.getenv("S3_BUCKET_FAQS")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
