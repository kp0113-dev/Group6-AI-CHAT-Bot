import os
import json
import boto3

# Model ID (set in Lambda environment vars for flexibility)
#   BEDROCK_MODEL_ID=ai21.jamba-1-5-large-v1:0
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "ai21.jamba-1-5-large-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

def _extract_answer(j):
    """Extracts text from Jamba 1.5 Large responses."""
    # Jamba 1.5 returns choices[0].message.content
    if "choices" in j and isinstance(j["choices"], list):
        first = j["choices"][0]
        if "message" in first and "content" in first["message"]:
            return first["message"]["content"].strip()

    # Fallbacks for other possible formats
    if "outputs" in j and isinstance(j["outputs"], list):
        for out in j["outputs"]:
            if "content" in out and isinstance(out["content"], list):
                for c in out["content"]:
                    if c.get("type") == "text" and "text" in c:
                        return c["text"]

    if "outputText" in j:
        return j["outputText"]

    if "output" in j and isinstance(j["output"], dict):
        msg = j["output"].get("message")
        if isinstance(msg, dict):
            return msg.get("content")

    for k in ("output_text", "content"):
        if k in j and isinstance(j[k], str):
            return j[k]

    return None


def lambda_handler(event, context):
    print("Bedrock Event:", json.dumps(event))

    question = event.get("question", "")
    db_result = event.get("dbResult", {})

    if db_result.get("status") == "FOUND":
        context_text = json.dumps(db_result["item"], indent=2)
    else:
        context_text = f"{db_result.get('status')} - {db_result.get('message', '')}"

    # Build a messages-style prompt for Jamba
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
                    "Only use the provided database info. "
                    "If the user asks for hours, reply only with opening and closing times. "
                    "If they ask for a location, reply with building name and address. "
                    "Be concise and factual, no extra words."
                )
            },
            {"role": "user", "content": user_content}
        ],
        "max_tokens": 150,
        "temperature": 0.0,
        "top_p": 0.9,
        "n": 1
    }

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )
        raw = json.loads(resp["body"].read())
        print("Jamba raw response:", json.dumps(raw, default=str))

        answer = _extract_answer(raw) or "Sorry, I couldn’t generate an answer."

    except Exception as e:
        answer = f"Error with Bedrock: {str(e)}"

    return {"answer": answer}
