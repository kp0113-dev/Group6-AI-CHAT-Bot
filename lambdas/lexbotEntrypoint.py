import json
import boto3
from datetime import datetime
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
    sessionId = event["sessionId"]
    intent_name = event["sessionState"]["intent"]["name"]
    slots = event["sessionState"]["intent"].get("slots", {})
    session_attrs = event["sessionState"].get("sessionAttributes", {})
    session_attrs["location"] = None
    logs_json = session_attrs.get("conversationLogs", "[]")
    logs = json.loads(logs_json)
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
            logs.append({
                "timestamp": datetime.utcnow().isoformat(),
                "userMessage": user_input,
                "botMessage": response_text
            })
            session_attrs["conversationLogs"] = json.dumps(logs)
            return {
                "sessionState": {
                    "sessionAttributes": session_attrs,
                    "dialogAction": {"type": "Delegate"},
                    "intent": event["sessionState"]["intent"]
                }
            }

    #----------------------------------------------------------------------------------------------------
    #----------------------------------------------------------------------------------------------------
    if (intent_name == "GetMap"):
        session_attrs["location"] = resolved_value
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
            }
        }
    #----------------------------------------------------------------------------------------------------
    #----------------------------------------------------------------------------------------------------

    if resolved_value is not None:
        # Call searchDynamoDB Lambda
        payload = {
            "intentName": intent_name,
            "resolvedValue": resolved_value,
            "question": user_input
        }
        response = lambda_client.invoke(
            FunctionName="searchDynamoDB-dev-kamil",
            InvocationType="RequestResponse",
            Payload=json.dumps(payload)
        )
        search_result = json.loads(response["Payload"].read())
        response_text = search_result
    
    # add the question and response + timestamp to the current conversation json
    logs.append({
        "timestamp": datetime.utcnow().isoformat(),
        "userMessage": user_input,
        "botMessage": response_text
    })
    session_attrs["conversationLogs"] = json.dumps(logs)
    
    # send the current conversation payload to 'saveConversations' lambda
    payload = {
        "sessionId": sessionId,
        "conversation": logs,
        "savedResolvedValue": session_attrs.get("savedResolvedValue", ""),
        "endedAt": datetime.utcnow().isoformat()
    }
    lambda_client.invoke(
        FunctionName="savedConversations-dev-kamil",
        InvocationType="Event",
        Payload=json.dumps(payload)
    )

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
