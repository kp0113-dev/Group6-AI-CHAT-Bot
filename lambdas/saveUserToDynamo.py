import json
import boto3

dynamo = boto3.resource('dynamodb')
table = dynamo.Table('ChargerGPT-Users')

def lambda_handler(event, context):
    # Try to parse body if it's a POST request
    if isinstance(event, dict) and "body" in event:
        try:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        except Exception:
            body = event
    else:
        body = event

    username = body.get("username")
    password = body.get("password")
    fullname = body.get("fullname")

    # Validate fields
    if not username or not password or not fullname:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing fields"})
        }

    # Prepare DynamoDB item
    try:
        table.put_item(
            Item={
                "username": username,
                "password": password,
                "fullname": fullname
            }
        )
        return {
            "statusCode": 200,
            "body": json.dumps({"success": True})
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
