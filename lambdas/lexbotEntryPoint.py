import json
import boto3

lambda_client = boto3.client("lambda")

def lambda_handler(event, context):
    # Debug log
    print("Received event:", json.dumps(event))

    # Extract Lex event info
    user_input = event.get("inputTranscript", "")
    intent_name = event["sessionState"]["intent"]["name"]
    slots = event["sessionState"]["intent"].get("slots", {})
    session_attrs = event["sessionState"].get("sessionAttributes", {})

    resolved_value = None

    # Resolve slot values
    for slot_name, slot_data in slots.items():
        if slot_data and "value" in slot_data:
            resolved_value_list = slot_data["value"].get("resolvedValues", [])
            if resolved_value_list:
                resolved_value = resolved_value_list[0]
                session_attrs["savedResolvedValue"] = resolved_value
            else:
                resolved_value = slot_data["value"].get("interpretedValue")

    # If no resolved value, fall back to session
    if resolved_value is None and "savedResolvedValue" in session_attrs:
        resolved_value = session_attrs["savedResolvedValue"]

    # If still no value, let Lex handle prompting
    if resolved_value is None:
        return {
            "sessionState": {
                "dialogAction": {"type": "Delegate"},
                "intent": event["sessionState"]["intent"]
            }
        }

    # Call Search Lambda
    payload = {
        "intentName": intent_name,
        "resolvedValue": resolved_value,
        "question": user_input
    }

    try:
        response = lambda_client.invoke(
            FunctionName="searchDynamoDB-dev-kyler",  
            InvocationType="RequestResponse",
            Payload=json.dumps(payload)
        )
        search_result = json.loads(response["Payload"].read())
    except Exception as e:
        print("Error invoking Search Lambda:", str(e))
        search_result = {"message": "There was an error looking up that location."}

    # Always provide a safe message
    message = (
        search_result.get("answer")
        or search_result.get("message")
        or "I couldn’t find anything."
    )

    # Return final response to Lex
    return {
        "sessionState": {
            "sessionAttributes": session_attrs,
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent_name, "state": "Fulfilled"}
        },
        "messages": [
            {"contentType": "PlainText", "content": message}
        ]
    }
