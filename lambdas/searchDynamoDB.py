import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

# Helper to convert DynamoDB Decimals into float (or str) (Because decimal is not JSON serializable )
def convert_decimals(obj):
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)  # can be replaced with string if needed
    return obj

def lambda_handler(event, context):
    """ Search Lambda:
        1. Tries get_item by partition key (fast).
        2. Falls back to a scan for case-insensitive matches.
        3. Converts Decimal → float for JSON safety.
        4. Calls Bedrock Lambda with result.
    """
    print("Search Event:", json.dumps(event))

    resolved_value = event["resolvedValue"]
    question = event.get("question", "")

    try:
        table = dynamodb.Table("GetLocation")
        print(f"Looking up locationName={resolved_value} in table {table.name}")

        # --- Step 1: Direct key lookup ---
        response = table.get_item(Key={"locationName": resolved_value})
        print("DynamoDB get_item response:", json.dumps(response, indent=2, default=str))

        item = response.get("Item")

        # --- Step 2: Fallback to scan if no item found ---
        if not item:
            print("get_item returned nothing, falling back to scan()")
            scan_response = table.scan()
            print("Scan results:", json.dumps(scan_response.get("Items", []), indent=2, default=str))

            for candidate in scan_response.get("Items", []):
                if candidate.get("locationName", "").lower().strip() == resolved_value.lower().strip():
                    item = candidate
                    print("Found match in scan:", json.dumps(item, indent=2, default=str))
                    break

        # --- Step 3: Build db_result ---
        if item:
            item = convert_decimals(item)
            db_result = {"status": "FOUND", "item": item}
        else:
            db_result = {
                "status": "NOT_FOUND",
                "message": f"No entry found for '{resolved_value}' in {table.name}."
            }

        # --- Step 4: Call Bedrock Lambda ---
        bedrock_payload = {"question": question, "dbResult": db_result}
        bedrock_response = lambda_client.invoke(
            FunctionName="bedrock_generate-dev-kyler",  
            InvocationType="RequestResponse",
            Payload=json.dumps(bedrock_payload)
        )
        return json.loads(bedrock_response["Payload"].read())

    except Exception as e:
        print("ERROR:", str(e))
        return {"status": "ERROR", "message": str(e)}
