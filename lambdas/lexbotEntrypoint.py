import json

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    # Get the user input text
    user_input = event.get("inputTranscript", "")

    # Get the current intent name
    intent_name = event["sessionState"]["intent"]["name"]

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
                "content": f"You said: {user_input}"
            }
        ]
    }
