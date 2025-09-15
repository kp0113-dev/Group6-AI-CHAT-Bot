import argparse
import json
from decimal import Decimal

import boto3


def load_buildings(table_name: str, path: str):
    ddb = boto3.resource("dynamodb")
    table = ddb.Table(table_name)
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f, parse_float=Decimal)
    with table.batch_writer() as batch:
        for it in items:
            batch.put_item(Item=it)
    print(f"Loaded {len(items)} buildings into {table_name}")


def load_schedules(table_name: str, path: str):
    ddb = boto3.resource("dynamodb")
    table = ddb.Table(table_name)
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f, parse_float=Decimal)
    with table.batch_writer() as batch:
        for it in items:
            batch.put_item(Item=it)
    print(f"Loaded {len(items)} schedules into {table_name}")


def load_instructors(table_name: str, path: str):
    ddb = boto3.resource("dynamodb")
    table = ddb.Table(table_name)
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f, parse_float=Decimal)
    with table.batch_writer() as batch:
        for it in items:
            batch.put_item(Item=it)
    print(f"Loaded {len(items)} instructors into {table_name}")


def main():
    parser = argparse.ArgumentParser(description="Load sample data into DynamoDB tables")
    parser.add_argument("--buildings-table", required=True)
    parser.add_argument("--schedules-table", required=True)
    parser.add_argument("--instructors-table", required=True)
    parser.add_argument("--buildings-file", default="../data/buildings.json")
    parser.add_argument("--schedules-file", default="../data/schedules.json")
    parser.add_argument("--instructors-file", default="../data/instructors.json")

    args = parser.parse_args()

    load_buildings(args.buildings_table, args.buildings_file)
    load_schedules(args.schedules_table, args.schedules_file)
    load_instructors(args.instructors_table, args.instructors_file)


if __name__ == "__main__":
    main()
