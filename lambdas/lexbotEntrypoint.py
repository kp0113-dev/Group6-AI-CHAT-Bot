import json

def lambda_handler(event, context):
    # Log the event for debugging
    print("Received event:", json.dumps(event))
    
    # return the same JSON back to Lex
    return event
