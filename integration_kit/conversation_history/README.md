# Conversation History Integration Kit

This kit extracts the conversation history feature so you can integrate it into another codebase with minimal friction.

Contents:
- `template-snippet.yaml`: SAM/CFN resources and IAM/env-vars to add.
- `memory_module.py`: Self-contained Python module for history persistence.
- `handler-snippet.py`: Example of how to wire the module into your Lex router handler.

## 1) Infrastructure (SAM/CFN)
Copy the `ConversationsTable` resource and router function environment/policy additions from `template-snippet.yaml` into your template. Key points:
- DynamoDB table with PK `user_id` (S) and SK `memory_key` (S), and TTL on `expires_at`.
- Router env vars:
  - `TABLE_CONVERSATIONS` (table name)
  - `FEATURE_CONVO_HISTORY` ("true"/"false")
  - `CONVERSATIONS_TTL_DAYS` (default 30)
- Router IAM: allow `dynamodb:GetItem, Query, Scan, PutItem` on the conversations table.

## 2) Drop-in Module
Place `memory_module.py` into an importable package in your Lambda code (e.g., beside your router file or in `your_pkg/memory_module.py`). It reads configuration from environment variables.

Exports:
- `get_user_id(event) -> str`
- `get_session_id(event) -> str`
- `load_persistent_memory(user_id) -> Dict[str,str]`
- `save_persistent_memory(user_id, session_attrs) -> None`
- `append_turn_history(user_id, event, response_message, session_attrs) -> None`
- `get_recent_turns(user_id, session_id, limit=10) -> List[Dict[str,Any]]`

## 3) Router Integration Example
See `handler-snippet.py` for:
- Import aliases (`mem_get_user_id`, `mem_get_session_id`, `mem_get_recent_turns`, `mem_append`, `mem_save`).
- Loading recent turns to build a compact `recent_context` string attached to `session_attrs`.
- Appending each assistant turn to the history and periodically persisting `session_attrs`.

Minimal steps in your handler:
1. Import memory helpers.
2. At start of `lambda_handler`, determine `user_id` and `session_id` from the Lex event.
3. Load and merge persistent memory into `session_attrs`.
4. Optionally attach `recent_context` to `session_attrs` for downstream logic.
5. On each reply, call `append_turn_history()` and `save_persistent_memory()`.

## 4) Data Model
- Partition key: `user_id`
- Sort key: `memory_key`
  - Persistent context row: `memory_key = "context"` (JSON-serialized `session_attrs` minus ephemeral keys)
  - Turn rows: `memory_key = f"session#{session_id}#turn#{timestamp_ms}"`
- Item shape for turn rows:
  ```json
  {
    "user_id": "<string>",
    "memory_key": "session#<session_id>#turn#<epoch_ms>",
    "expires_at": <epoch_seconds>,
    "data": {
      "user_input": "...",
      "assistant_response": "...",
      "intent": "...",
      "slots": {...},
      "session_attrs": {...},
      "timestamp_ms": <epoch_ms>,
      "session_id": "<string>"
    }
  }
  ```

## 5) Environment Variables
- `TABLE_CONVERSATIONS` (required): DynamoDB table name
- `FEATURE_CONVO_HISTORY` (optional): enable/disable history writes (default true)
- `CONVERSATIONS_TTL_DAYS` (optional): TTL days for turn records (default 30)
- `DEFAULT_STUDENT_ID` (optional): user_id fallback if Lex does not provide one

## 6) Notes
- The module is defensive: on any exception, it returns safely without affecting user replies.
- Excludes ephemeral fields such as `recent_context` from persistent context saves.
- Query pattern uses `begins_with(memory_key, :prefix)` to fetch recent session turns.
