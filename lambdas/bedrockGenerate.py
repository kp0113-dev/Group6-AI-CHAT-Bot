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

    # User-side content: reinforce “only use DB info” and “no extra stuff”
    user_content = (
        f'The user asked: "{question}"\n'
        f"Here is the database information you may use:\n{context_text}\n\n"
        "Using only this information, answer the user's question. "
        "Answer the entire question, but do not add details the user did not ask for."
    )

    body = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful campus assistant that answers questions about campus locations and related info. "
                    "You must use ONLY the information provided in the database context. "
                    "If the context does not contain the answer, clearly say that you do not have that information.\n\n"

                    "GENERAL RULES:\n"
                    "- Always answer in complete sentences.\n"
                    "- Sound natural and human, not like a JSON dump.\n"
                    "- Fully answer everything the user actually asked.\n"
                    "- Do not add extra information beyond what is needed to answer the question.\n"
                    "- Never invent details or guess beyond the database context.\n"
                    "- Never mention the database or the context explicitly.\n\n"

                    "HOW TO USE THE CONTEXT:\n"
                    "- Treat the database fields (such as name, locationName, address, building, hours, "
                    "description, services, phone, email, website, notes, etc.) as facts you can turn into natural sentences.\n"
                    "- Only mention fields that are relevant to the user’s question.\n"
                    "- If a relevant field is missing or empty, say that you don't have that information.\n\n"

                    "INTENT-SPECIFIC GUIDELINES (USE WHEN APPLICABLE):\n"
                    "- LOCATION / WHERE questions:\n"
                    "  Use a sentence like: 'The [locationName] is located at [address] in the [building].'\n"
                    "- HOURS / WHEN questions:\n"
                    "  Use a sentence like: 'The [locationName]'s hours are [hours].'\n"
                    "- WHAT / SERVICES questions (for example, 'What is this place?' or 'What do they do there?'):\n"
                    "  Use a sentence like: 'The [locationName] is [description] and provides [services].'\n"
                    "- CONTACT questions (for example, phone or email):\n"
                    "  Use a sentence like: 'You can contact the [locationName] at [phone] or [email].'\n"
                    "- WEBSITE / MORE INFO questions:\n"
                    "  Use a sentence like: 'For more information about the [locationName], visit [website].'\n"
                    "- MULTI-PART questions (for example, 'Where is it and what are the hours?'):\n"
                    "  Answer all parts in 1–4 concise sentences, without repeating the same detail multiple times.\n\n"

                    "IF INFORMATION IS MISSING:\n"
                    "- If the database does not have the answer to the user’s question, say something like: "
                    "'I’m sorry, but I don’t have that information for [locationName].'\n"
                    "- Do not make anything up.\n"
                ),
            },
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 150,
        "temperature": 0.2,  # Slightly higher for more human-like but still controlled answers
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

