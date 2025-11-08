import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('SavedConversations-prod')

def lambda_handler(event, context):
    print ("we got here 2")
    try:
        response = table.query(
            IndexName='GSI_SessionEndedAt',
            KeyConditionExpression=Key('GSI_PK').eq('Session'),
            ScanIndexForward=False,  # newest first
            Limit=3
        )
        print ("we got here 1")
        items = response.get('Items', [])
        session_ids = [item['sessionId'] for item in items]
        times = [item['endedAt']for item in items]

        print (session_ids)

        return {"sessionIds": session_ids,
                "times": times}

    except Exception as e:
        return {"error": str(e)}
