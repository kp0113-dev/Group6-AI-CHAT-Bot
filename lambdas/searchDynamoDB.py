import json
import boto3

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

def lambda_handler(event, context):
    # Print statement for debugging in CloudWatch
    print("Dynamo search request:", json.dumps(event))

    intent_name = event["intentName"]
    resolved_value = event["resolvedValue"]
    question = event.get("question", "")

    try:
        table = dynamodb.Table(intent_name.split("-")[0])  # Table name = (left side of -) ex. "BuildingInfo"-GetTime
        response = table.get_item(Key={"value": resolved_value})
        item = response.get("Item", {})

        if "Item" in response:
            db_result = {"status": "FOUND", "item": item}
            # Call Bedrock Lambda
            bedrock_payload = {"question": question, "dbResult": db_result}
            bedrock_response = lambda_client.invoke(
                FunctionName="bedrock_generate-dev-kyler",  
                InvocationType="RequestResponse",
                Payload=json.dumps(bedrock_payload)
            )
            data = json.loads(bedrock_response["Payload"].read())
            result = data['answer']
        else:
            result = f"No data found for '{resolved_value}' in {intent_name.split('-')[0]} database."

    except Exception as e:
        result = f"Error querying DynamoDB: {str(e)}"

    return result
    
