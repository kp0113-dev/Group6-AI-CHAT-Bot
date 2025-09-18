import json
import boto3

dynamodb = boto3.resource("dynamodb")

def lambda_handler(event, context):
    print("Dynamo search request:", json.dumps(event))

    intent_name = event["intentName"]
    resolved_value = event["resolvedValue"]

    try:
        table = dynamodb.Table(intent_name)  # Each intent = table
        response = table.get_item(Key={"locationName": resolved_value})

        if "Item" in response:
            # Return the raw item back, not just a string
            result = {
                "status": "FOUND",
                "item": response["Item"]
            }
        else:
            result = {
                "status": "NOT_FOUND",
                "message": f"No entry found for '{resolved_value}' in {intent_name} table."
            }

    # Call Bedrock Lambda
    bedrock_payload = {
        "question" = : user_input,
        "result" : search_result
    }
    bedrock_response = lambda_client.invoke(
        FunctionName="bedrockGenerate-dev-kyler",
        InvocationType="RequestResponse",
        Payload=json.dumps(bedrock_payload)
    )
    bedrock_result = json.loads(bedrock_response["Payload"].read())


    except Exception as e:
        result = {
            "status": "ERROR",
            "message": str(e)
        }

    return result
