import json
import boto3

bedrock = boto3.client("bedrock-runtime")

def lambda_handler(event, context):
    """
    Input Example:
    {
      "question": "Where is the cafeteria?",
      "dbResult": {
        "status": "FOUND",
        "item": {
          "locationName": "cafeteria",
          "building": "Main Hall",
          "hours": "8am - 5pm"
        }
      }
    }
    """

    print("Bedrock request:", json.dumps(event))

    question = event.get("question", "")
    db_result = event.get("dbResult", {})

    # Prepare context
    if db_result.get("status") == "FOUND":
        context_text = f"Database info:\n{json.dumps(db_result['item'], indent=2)}"
    else:
        context_text = f"Database lookup result: {db_result.get('status')} - {db_result.get('message', '')}"

    # Build Bedrock prompt
    prompt = f"""
    The user asked: "{question}"

    Context:
    {context_text}

    Answer the user in a helpful, natural way.
    """

    try:
        response = bedrock.invoke_model(
            modelId="anthropic Claude 3.5 Sonnet v2 ",  
            body=json.dumps({
                "prompt": prompt,
                "max_tokens_to_sample": 300
            }),
            contentType="application/json",
            accept="application/json"
        )

        response_body = json.loads(response["body"].read())
        answer = response_body.get("completion", "Sorry, I couldn’t generate an answer.")

    except Exception as e:
        answer = f"Error with Bedrock: {str(e)}"

    return {
        "answer": answer
    }
