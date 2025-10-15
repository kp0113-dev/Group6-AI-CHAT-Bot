import boto3

dynamodb = boto3.client('dynamodb')

def lambda_handler(event, context):
    print(event)
    session_id = event.get('sessionId')
    if not session_id:
        return {"error": "Missing sessionId"}
    
    try:
        response = dynamodb.get_item(
            TableName="SavedConversations-prod",
            Key={"sessionId": {"S": session_id}},
            ProjectionExpression="conversation"
        )
        item = response.get("Item")
        if not item:
            return {"error": "Session not found"}
        print(item)
        return {"conversation": item["conversation"]["L"]}
    
    except Exception as e:
        return {"error": str(e)}
