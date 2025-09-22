import argparse
import boto3
import json
import hashlib
import time
import os

dynamodb = boto3.client("dynamodb")
s3 = boto3.client("s3")

# optional: store hash in an S3 bucket
HASH_BUCKET = os.getenv("DEPLOY_STATE_BUCKET", "my-dynamodb-deploy-state")

def get_file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

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
        table_def = json.load(f)

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

def store_hash(table_name, file_hash):
    key = f"{table_name}.hash"
    s3.put_object(Bucket=HASH_BUCKET, Key=key, Body=file_hash.encode("utf-8"))

def get_stored_hash(table_name):
    key = f"{table_name}.hash"
    try:
        obj = s3.get_object(Bucket=HASH_BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8")
    except s3.exceptions.NoSuchKey:
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-template", required=True)
    parser.add_argument("--items-file", required=True)
    args = parser.parse_args()

    with open(args.table_template) as f:
        template = json.load(f)

    table_name = template["TableName"]
    file_hash = get_file_hash(args.items_file)
    stored_hash = get_stored_hash(table_name)

    if not table_exists(table_name):
        print("Table does not exist → creating...")
        create_table(args.table_template)
        put_items(table_name, args.items_file)
        store_hash(table_name, file_hash)

    elif file_hash != stored_hash:
        print("Items JSON changed → redeploying...")
        delete_table(table_name)
        create_table(args.table_template)
        put_items(table_name, args.items_file)
        store_hash(table_name, file_hash)

    else:
        print("No changes → skipping table deployment.")
