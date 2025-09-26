import json
import boto3

dynamodb = boto3.resource("dynamodb")

def lambda_handler(event, context):
    # Print statement for debugging in CloudWatch
    print("Dynamo search request:", json.dumps(event))

    intent_name = event["intentName"]
    resolved_value = event["resolvedValue"]

    try:
        table = dynamodb.Table(intent_name.split("-")[0])  # Table name = (left side of -) ex. "BuildingInfo"-GetTime
        response = table.get_item(Key={"value": resolved_value})

        if "Item" in response:
            result = f"Found: {response['Item']}"
        else:
            result = f"No entry found for '{resolved_value}' in {intent_name} table."

    except Exception as e:
        result = f"Error querying DynamoDB: {str(e)}"

    return {
        "result": result
    }
    
