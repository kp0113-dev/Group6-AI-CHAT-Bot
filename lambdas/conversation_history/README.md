# Conversation History Package

This package enables session-scoped conversation logging for a Lex V2 Lambda code hook.

## Environment Variables
- `TABLE_CONVERSATIONS`: DynamoDB table name (required)
- `FEATURE_CONVO_HISTORY`: "true" to enable writes (default: true)
- `CONVERSATIONS_TTL_DAYS`: TTL days for turn rows (default: 30)
- `DEFAULT_STUDENT_ID`: Optional fallback user id if Lex event lacks one

## DynamoDB Table Schema
- Partition key: `user_id` (String)
- Sort key: `memory_key` (String)
- TTL attribute: `expires_at` (enabled)

Row types:
- Persistent context row: `memory_key = "context"` (JSON-serialized `session_attrs` minus ephemeral keys)
- Turn rows: `memory_key = "session#<session_id>#turn#<timestamp_ms>"`

## Required IAM
Attach to the Lambda execution role:
```
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:PutItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:<REGION>:<ACCOUNT_ID>:table/<TABLE_NAME>"
      ]
    }
  ]
}
```

## Integration Example
In your Lex router (e.g., `lambdas/lexbotEntrypoint.py`):
```python
from lambdas.conversation_history.memory_module import (
    get_user_id as mem_get_user_id,
    append_turn_history as mem_append,
    save_persistent_memory as mem_save,
)

# ... build response_body ...
try:
    user_id = mem_get_user_id(event)
    mem_append(user_id, event, str(response_text), session_attrs)
    mem_save(user_id, session_attrs)
except Exception:
    pass
```

## Notes
- The module is defensive; it no-ops if env/table are not configured.
- Excludes ephemeral fields like `recent_context` from persistent context saves.
- Query pattern uses `begins_with(memory_key, :prefix)` with `prefix = f"session#{session_id}#"`.
