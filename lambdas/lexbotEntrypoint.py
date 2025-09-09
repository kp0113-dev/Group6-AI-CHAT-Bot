import json
import boto3

lambda_client = boto3.client("lambda")

def lambda_handler(event, context):
    # Print statement for Debugging in CloudWatch
    print("Received event:", json.dumps(event))

    # Get the user input text
    user_input = event.get("inputTranscript", "")
    
    # Set default response
    response_text = "Deafult Response"

    # Get the current intent items
    intent_name = event["sessionState"]["intent"]["name"]
    slots = event["sessionState"]["intent"].get("slots", {})
    interpreted_value = None
    
    if "location" in slots and slots["location"] and "value" in slots["location"]:
        interpreted_value = slots["location"]["value"].get("interpretedValue")

    if not interpreted_value:
        response_text = f"Could not determine interpreted value for {intent_name}"
    else:
        # Call searchDynamoDB Lambda
        payload = {
            "intentName": intent_name,
            "interpretedValue": interpreted_value
        }
        response = lambda_client.invoke(
            FunctionName="searchDynamoDB-dev-kamil",
            InvocationType="RequestResponse",
            Payload=json.dumps(payload)
        )
        search_result = json.loads(response["Payload"].read())
        response_text = search_result.get("result", "No result returned.")
        
    # MAIN RETURN RESPONSE
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Close"   # End the conversation
            },
            "intent": {
                "name": intent_name,
                "state": "Fulfilled"
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": f"{response_text}"
            }
        ]
    }
