import argparse
import json
from typing import Optional

import boto3


def get_table(table_name: str):
    ddb = boto3.resource("dynamodb")
    return ddb.Table(table_name)


def get_memory(table_name: str, user_id: str) -> Optional[dict]:
    table = get_table(table_name)
    resp = table.get_item(Key={"user_id": user_id, "memory_key": "context"})
    item = resp.get("Item")
    if not item:
        return None
    data = item.get("data")
    try:
        return json.loads(data) if isinstance(data, str) else data
    except Exception:
        return {"raw": data}


def clear_memory(table_name: str, user_id: str) -> None:
    table = get_table(table_name)
    table.delete_item(Key={"user_id": user_id, "memory_key": "context"})


def main():
    parser = argparse.ArgumentParser(description="Admin tool to view/clear conversation memory")
    parser.add_argument("--table", required=True, help="Conversations table name")
    parser.add_argument("--user-id", required=True, help="User ID to inspect")
    parser.add_argument("--clear", action="store_true", help="Clear memory for the user")
    args = parser.parse_args()

    if args.clear:
        clear_memory(args.table, args.user_id)
        print(f"Cleared memory for user_id={args.user_id}")
        return

    mem = get_memory(args.table, args.user_id)
    if mem is None:
        print("No memory found.")
    else:
        print(json.dumps(mem, indent=2))


if __name__ == "__main__":
    main()
