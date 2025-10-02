import os
import json
import boto3


# Use Jamba 1.5 Large by default
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "ai21.jamba-1-5-large-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


def _extract_answer(j: dict) -> str | None:
    """
    Extract text from Jamba 1.5 Large responses.

    The helper tries a few common shapes:
    - {"choices": [{"message": {"content": "..."}}]}
    - {"outputs": [{"content": [{"text": "..."}]}]}
    """
    # OpenAI/Chat-like shape
    if isinstance(j, dict) and "choices" in j and isinstance(j["choices"], list):
        first = j["choices"][0]
        msg = first.get("message", {})
        content = msg.get("content")
        if isinstance(content, str):
            return content.strip()

    # AI21/Bedrock alt shape (defensive)
    if isinstance(j, dict) and "outputs" in j and isinstance(j["outputs"], list):
        out0 = j["outputs"][0]
        content = out0.get("content")
        if isinstance(content, list) and content and isinstance(content[0], dict):
            text = content[0].get("text")
            if isinstance(text, str):
                return text.strip()

    return None


def lambda_handler(event, context):
    print("Bedrock Event:", json.dumps(event))

    question = event.get("question", "")
    db_result = event.get("dbResult", {})

    # Build context from DynamoDB result
    if db_result.get("status") == "FOUND":
        context_text = json.dumps(db_result.get("item", {}), indent=2)
    else:
        context_text = f"{db_result.get('status')} - {db_result.get('message', '')}"

    user_content = (
        f'The user asked: "{question}"\n'
        f"Context:\n{context_text}\n\n"
        "Answer the user using only the database info."
    )

    body = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful campus assistant. "
                    "Always answer in a full sentence. "
                    "If the user asks 'where', respond with: "
                    "'The [locationName] is located at [address] in the [name].' "
                    "If they ask about hours, respond with: "
                    "'The [locationName]'s hours are [hours].' "
                    "Be concise and factual."
                ),
            },
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 150,
        "temperature": 0.0,
    }

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        # Bedrock returns a streaming body-like object; read() to get bytes
        raw = json.loads(resp["body"].read())
        print("Jamba raw response:", json.dumps(raw, default=str))

        answer = _extract_answer(raw) or "Sorry, I couldn’t generate an answer."

    except Exception as e:
        answer = f"Error with Bedrock: {str(e)}"

    return {"answer": answer}
