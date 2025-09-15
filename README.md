
# ChargerGPT – UAH Campus Chatbot (AWS)

An AWS-first chatbot using Amazon Lex, AWS Lambda (Python 3.12), DynamoDB, S3, and CloudWatch. Optional Bedrock fallback can be enabled later. Region: us-east-1.

## Architecture Overview

- Users interact via Amazon Lex (console for MVP testing).
- Lex intents call a single Lambda function `charger_gpt/handler.lambda_handler`.
- Lambda reads structured data from DynamoDB (buildings, schedules, instructors).
- Lambda reads FAQs from S3 (`faqs/faqs.json`).
- Logs emitted to CloudWatch.

Key resources are defined in `template.yaml` (AWS SAM). Deploy with SAM for repeatability; console steps are also provided below.

## Lex Intents & Design (Lex V2)

Create a Lex V2 bot (English, `en_US`) with these intents and slots. Configure a Lambda fulfillment hook pointing to the Lambda created by this project.

### Intents

1. `GetBuildingHoursIntent`

   - Slots:
     - `BuildingName` (AMAZON.Person or custom slot – simple string)
   - Sample utterances:
     - "What are the hours for {BuildingName}?"
     - "When is {BuildingName} open?"
     - "{BuildingName} hours"
2. `GetCampusLocationIntent`

   - Slots:
     - `BuildingName`
   - Sample utterances:
     - "Where is {BuildingName}?"
     - "How do I get to {BuildingName}?"
     - "Location of {BuildingName}"
3. `GetFAQIntent`

   - Slots:
     - `FaqTopic` (free-text)
   - Sample utterances:
     - "What is the campus dress code?"
     - "What's the number for campus security?"
     - "Ask about {FaqTopic}"
4. `GetClassScheduleIntent` (feature-flagged)

   - Slots:
     - `CourseCode` (e.g., CS101, ECE301)
   - Sample utterances:
     - "Where is my {CourseCode} class?"
     - "When is {CourseCode}?"
5. `GetInstructorLookupIntent` (feature-flagged)

   - Slots:
     - `CourseCode`
   - Sample utterances:
     - "Who teaches {CourseCode}?"
     - "Instructor for {CourseCode}"
6. `FallbackIntent`

   - Standard Lex fallback, routed to Lambda for a friendly message.

### Fulfillment Hook

- Enable Lambda fulfillment for all intents above.
- Use `Closing response` from Lambda (the Lambda returns `Close`).

## Lambda Functions (Python 3.12)

- Single handler: `lambdas/charger_gpt/handler.py`.
- Shared Lex helpers: `lambdas/charger_gpt/utils.py`.
- Environment variables are defined in `template.yaml` and include table names and S3 bucket name.

Logging: controlled with `LOG_LEVEL`. All logs are visible in CloudWatch under the function's log group.

Feature flags (env vars):

- `FEATURE_BEDROCK` (default `false`)
- `FEATURE_SCHEDULES` (default `true` via code)
- `FEATURE_INSTRUCTORS` (default `true` via code)

## DynamoDB Table Design

Tables (created by `template.yaml`):

- Buildings: `${ProjectPrefix}-${Stage}-buildings`
  - PK: `building_id` (S)
  - Attributes: `name`, `hours`, `address`, `lat`, `lon`
  - Simple scans by `name` are used for MVP (OK for small dataset). Add a GSI on `name` later if needed.
- Schedules: `${ProjectPrefix}-${Stage}-schedules`
  - PK: `student_id` (S), SK: `course_code` (S)
  - Attributes: `building`, `location`, `time`
- Instructors: `${ProjectPrefix}-${Stage}-instructors`
  - PK: `course_code` (S)
  - Attributes: `instructor_name`, `email`, `office`

## S3 Bucket Structure

- `${ProjectPrefix}-${Stage}-faqs-<account>-<region>` (created by `template.yaml`)
  - `faqs/faqs.json` – uploaded using `scripts/upload_s3_faqs.py`

Sample data files are included under `data/`:

- `data/buildings.json`
- `data/schedules.json`
- `data/instructors.json`
- `data/faqs.json`

## Deployment Instructions (AWS SAM)

Prereqs:

- AWS CLI configured to `us-east-1`
- AWS SAM CLI installed
- Python 3.12

Build and deploy:

```bash
sam build --use-container
sam deploy --stack-name chargergpt-dev --resolve-s3 --capabilities CAPABILITY_IAM \
  --parameter-overrides ProjectPrefix=chargergpt Stage=dev
```

Outputs will include DynamoDB table names and the FAQs bucket. Note the bucket name for the next step.

### Load Sample Data

Use the scripts from the repo root (adjust paths if needed):

```bash
# Upload FAQs to S3
python ChargerGPT/scripts/upload_s3_faqs.py <FaqsBucketNameFromOutput> ChargerGPT/data/faqs.json

# Load DynamoDB tables
python ChargerGPT/scripts/load_dynamodb.py \
  --buildings-table chargergpt-dev-buildings \
  --schedules-table chargergpt-dev-schedules \
  --instructors-table chargergpt-dev-instructors \
  --buildings-file ChargerGPT/data/buildings.json \
  --schedules-file ChargerGPT/data/schedules.json \
  --instructors-file ChargerGPT/data/instructors.json
```

## Lex Setup (Console, V2)

1. Create bot: `ChargerGPT` (English `en_US`).
2. Create intents and slots as listed earlier.
   - Slot types: basic `AMAZON.AlphaNumeric` or `AMAZON.SearchQuery` for `FaqTopic`.
3. In `Aliases` > your alias (e.g., `TestBotAlias`), enable `Lambda fulfillment` and select the Lambda from this stack.
4. Build the bot, then test in the Lex console.

## Testing Instructions

Use the Lex test console and try:

- "What are the hours for the library?"
- "Where is the engineering building?"
- "What is the campus dress code?"
- "Who teaches ECE301 this semester?" (feature-flagged path uses DynamoDB sample)
- "Where is my CS101 class?" (uses schedules table)

Check CloudWatch logs:

- Navigate to CloudWatch > Log groups > `/aws/lambda/chargergpt-dev-handler` (or your name).
- Review recent logs for request/response.

## Optional Bedrock Integration (disabled by default)

- After your account is granted access to Bedrock and a model (e.g., Claude), set env vars on the function:
  - `FEATURE_BEDROCK=true`
  - `BEDROCK_MODEL_ID=<provider.modelId>` (e.g., `anthropic.claude-3-sonnet-20240229-v1:0`)
- Add IAM permission `bedrock:InvokeModel` to the function role (lines are commented in `template.yaml`).
- Extend `handle_faq` to call Bedrock when no match is found, using a prompt like:

```
You are ChargerGPT, a helpful assistant for The University of Alabama in Huntsville (UAH).
Answer concisely. If unsure, say you don't know.
User question: "{question}"
Relevant context: campus FAQs may include safety, hours, buildings, contacts.
```

## Console-Based Deployment (alternative to SAM)

- Manually create DynamoDB tables and S3 bucket per names above.
- Create a new Lambda function (Python 3.12) and upload `lambdas/` code as a .zip.
- Set environment variables to the resource names.
- Attach IAM permissions: DynamoDB read, S3 read, CloudWatch logs.
- Point Lex fulfillment to the Lambda.

## Scaling Suggestions

- Add a GSI on `BuildingsTable` for `name` to avoid scans.
- Add more building synonyms and alias slot values in Lex.
- Cache S3 FAQs in memory and refresh by S3 event or TTL.
- Add Cognito + a web UI for student login to personalize schedules.
- Replace scans with parameterized queries where possible.
