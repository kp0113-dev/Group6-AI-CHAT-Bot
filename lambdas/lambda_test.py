import json

def lambda_handler(event, context):
    print("Received event from Lex:")
    print(json.dumps(event))

    intent_name = event["currentIntent"]["name"]

    if intent_name == "AskLocation":
        answer = "The charger cafe is at University Cir, Huntsville, AL 35816"
    elif intent_name == "AskTime":
        answer = "The charger cafe opens at 11am and closes at 8pm with a break between 3-4:30."
    else:
        answer = "Sorry, I don’t know that one."

    response = {
        "sessionAttributes": event.get("sessionAttributes", {}),
        "dialogAction": {
            "type": "Close",
            "fulfillmentState": "Fulfilled",
            "message": {
                "contentType": "PlainText",
                "content": answer
            }
        }
    }

    return response
