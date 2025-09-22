import argparse
import boto3
import json
import os

dynamodb = boto3.client("dynamodb")


def table_exists(table_name):
    try:
        dynamodb.describe_table(TableName=table_name)
        return True
    except dynamodb.exceptions.ResourceNotFoundException:
        return False


def delete_table(table_name):
    print(f"Deleting table {table_name}...")
    dynamodb.delete_table(TableName=table_name)
    waiter = dynamodb.get_waiter("table_not_exists")
    waiter.wait(TableName=table_name)


def create_table(template_path):
    with open(template_path) as f:
        template_str = f.read().replace("__BRANCH_SUFFIX__", os.getenv("branch_suffix", "local"))
        table_def = json.loads(template_str)

    print(f"Creating table {table_def['TableName']}...")
    dynamodb.create_table(**table_def)
    waiter = dynamodb.get_waiter("table_exists")
    waiter.wait(TableName=table_def["TableName"])
    return table_def["TableName"]


def put_items(table_name, items_path):
    with open(items_path) as f:
        items = json.load(f)

    db = boto3.resource("dynamodb")
    table = db.Table(table_name)

    print(f"Inserting {len(items)} items into {table_name}...")
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-template", required=True)
    parser.add_argument("--items-file", required=True)
    args = parser.parse_args()

    with open(args.table_template) as f:
        template_str = f.read().replace("__BRANCH_SUFFIX__", os.getenv("branch_suffix", "local"))
        template = json.loads(template_str)

    table_name = template["TableName"]

    if table_exists(table_name):
        print(f"Table {table_name} exists → redeploying...")
        delete_table(table_name)

    create_table(args.table_template)
    put_items(table_name, args.items_file)
