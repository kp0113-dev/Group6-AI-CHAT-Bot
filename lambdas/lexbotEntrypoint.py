import json
import boto3
from lambdas.heuristics.heuristics import can_reuse_subject


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
    session_attrs = event["sessionState"].get("sessionAttributes", {})
    resolved_value = None
   
    # Check if intent is fulfilled and check if slot has 'value'
    # If slot value exists then set the resolved value
    # If slot value exists but resolved value does not then default to interpreted value
    for slot_name, slot_data in slots.items():
        if slot_data and "value" in slot_data:
            resolved_value_list = slot_data["value"].get("resolvedValues", [])
            try:
                resolved_value = resolved_value_list[0] # resolved_value returns as a list so pull the value from the first index
                session_attrs["savedResolvedValue"] = resolved_value # update saved subject value
            except IndexError:
                resolved_value = slots["location"]["value"].get("originalValue")
                session_attrs["savedResolvedValue"] = resolved_value  # update saved subject value
            print(f"Resolved value for {slot_name}: {resolved_value}")


    # Return back to Lex and invoke slot prompt asking user to specify slot value
    if resolved_value is None:
        if can_reuse_subject(intent_name) and "savedResolvedValue" in session_attrs:
            resolved_value = session_attrs["savedResolvedValue"]
        else:
            return {
                "sessionState": {
                    "dialogAction": {"type": "Delegate"},
                    "intent": event["sessionState"]["intent"]
                }
            }

    if resolved_value is not None:
        # Call searchDynamoDB Lambda
        payload = {
            "intentName": intent_name,
            "resolvedValue": resolved_value,
            "question": user_input
        }
        response = lambda_client.invoke(
            FunctionName="searchDynamoDB-dev-kpatel",
            InvocationType="RequestResponse",
            Payload=json.dumps(payload)
        )
        search_result = json.loads(response["Payload"].read())
        response_text = search_result
       
    # MAIN RETURN RESPONSE
    return {
        "sessionState": {
            "sessionAttributes": session_attrs,
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
