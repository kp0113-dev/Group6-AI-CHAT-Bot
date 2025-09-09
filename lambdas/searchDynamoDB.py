import json
import boto3

dynamodb = boto3.resource("dynamodb")

def lambda_handler(event, context):
    # Print statement for debugging in CloudWatch
    print("Dynamo search request:", json.dumps(event))

    intent_name = event["intentName"]
    interpreted_value = event["interpretedValue"]

    try:
        table = dynamodb.Table(intent_name)  # Table name = intent name
        response = table.get_item(Key={"locationName": interpreted_value})

        if "Item" in response:
            result = f"Found: {response['Item']}"
        else:
            result = f"No entry found for '{interpreted_value}' in {intent_name} table."

    except Exception as e:
        result = f"Error querying DynamoDB: {str(e)}"

    return {
        "result": result
    }
