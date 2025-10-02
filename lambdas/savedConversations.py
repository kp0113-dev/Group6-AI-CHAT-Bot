import json
import boto3
import time
from datetime import datetime
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("SavedConversations")
ttl_value = int(time.time()) + (3 * 24 * 60 * 60)  # now + 3 days

def lambda_handler(event, context):
    try:
        session_id = event.get("sessionId")
        new_conversation = event.get("conversation", [])
        ended_at = event.get("endedAt", datetime.utcnow().isoformat())

        if not session_id:
            raise ValueError("Missing sessionId in event")

        # First, try to get the existing item
        response = table.get_item(Key={"sessionId": session_id})
        existing_item = response.get("Item")

        if existing_item:
            # Session exists → update conversation and endedAt
            updated_conversation = new_conversation  # Replace, or append to existing if needed

            # Use update_item to modify specific attributes
            table.update_item(
                Key={"sessionId": session_id},
                UpdateExpression="SET conversation = :conv, endedAt = :end",
                ExpressionAttributeValues={
                    ":conv": updated_conversation,
                    ":end": ended_at
                }
            )
        else:
            # Session does not exist → create new item
            item = {
                "sessionId": session_id,
                "endedAt": ended_at,
                "conversation": new_conversation,
                "expirationTime": ttl_value
            }
            table.put_item(Item=item)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Conversation saved", "sessionId": session_id})
        }

    except ClientError as e:
        print(f"DynamoDB error: {e.response['Error']['Message']}")
        return {"statusCode": 500, "body": "DynamoDB error"}
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"statusCode": 500, "body": "Internal server error"}
