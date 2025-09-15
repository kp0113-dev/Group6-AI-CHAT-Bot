import argparse
import json
import os

import boto3


def main():
    parser = argparse.ArgumentParser(description="Upload FAQs JSON to S3")
    parser.add_argument("bucket", help="Target S3 bucket name")
    parser.add_argument("faqs_file", help="Path to faqs.json")
    args = parser.parse_args()

    s3 = boto3.client("s3")

    key = "faqs/faqs.json"
    with open(args.faqs_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    body = json.dumps(data).encode("utf-8")

    s3.put_object(Bucket=args.bucket, Key=key, Body=body, ContentType="application/json")
    print(f"Uploaded {args.faqs_file} to s3://{args.bucket}/{key}")


if __name__ == "__main__":
    main()
