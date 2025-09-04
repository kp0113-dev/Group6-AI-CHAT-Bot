import java 
def lambda_handler(event, context):
    #Log what LexBot sent to Lambda
    print("Recieved event from Lexbot")
    print("Recieved text from Lexbot")
    print(json.dumps event)
    return java.lang.System.getProperty("java.version")
    return "Hello from Lambda"

#Used to access LexBot
user_input = event.get("inputTrnascript", "No input provided")

#Returns to lex with a simple message
response = {
    "dialogAction": {
        "type": "Close",
        "fulfillmentState": "Fulfilled",
        "message": {
            "contentType": "PlainText",
            "content": "Hello from Lambda, input recieved: {user_input}"
        }
    }
}
return response 
