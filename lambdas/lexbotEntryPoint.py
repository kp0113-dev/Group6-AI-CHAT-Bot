import json
import boto3

lambda_client = boto3.client("lambda")

def lambda_handler(event, context):
    """ Entry Lambda: Handles Lex input and calls the Search Lambda """
    print("Lex Event:", json.dumps(event))

    # Extract intent and slots
    intent_name = event["sessionState"]["intent"]["name"]
    slots = event["sessionState"]["intent"].get("slots", {})
    session_attrs = event["sessionState"].get("sessionAttributes", {})

    # Get the slot value (interpretedValue is the raw text Lex captured)
    location_value = None
    if slots.get("location") and "value" in slots["location"]:
        location_value = slots["location"]["value"].get("interpretedValue")

    if not location_value:
        # If Lex hasn’t captured a slot yet, delegate back
        return {
            "sessionState": {
                "dialogAction": {"type": "Delegate"},
                "intent": event["sessionState"]["intent"]
            }
        }

    # Call the Search Lambda
    payload = {
        "intentName": intent_name,
        "resolvedValue": location_value,
        "question": event.get("inputTranscript", "")
    }

    response = lambda_client.invoke(
        FunctionName="searchDynamoDB-dev-kyler",   
        InvocationType="RequestResponse",
        Payload=json.dumps(payload)
    )
    search_result = json.loads(response["Payload"].read())

    # Send Bedrock-generated answer back to Lex
    return {
        "sessionState": {
            "sessionAttributes": session_attrs,
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent_name, "state": "Fulfilled"}
        },
        "messages": [
            {"contentType": "PlainText", "content": search_result.get("answer", "I couldn’t find anything.")}
        ]
    }
