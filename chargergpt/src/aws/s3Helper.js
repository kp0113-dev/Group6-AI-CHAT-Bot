// src/aws/s3Helper.js
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { fromCognitoIdentityPool } from "@aws-sdk/credential-provider-cognito-identity";

const REGION = window._env_?.REGION;
const IDENTITY_POOL_ID = window._env_?.IDENTITY_POOL_ID;
const BUCKET_NAME = "lexbot-campus-maps"; // 👈 your bucket name

const s3Client = new S3Client({
  region: REGION,
  credentials: fromCognitoIdentityPool({
    identityPoolId: IDENTITY_POOL_ID,
    clientConfig: { region: REGION },
  }),
});

export const getMapImageUrl = async (location) => {
  try {
    const key = `${location.toLowerCase()}.jpg`;
    const command = new GetObjectCommand({ Bucket: BUCKET_NAME, Key: key });
    const response = await s3Client.send(command);

    const blob = await new Response(response.Body).blob();
    return URL.createObjectURL(blob);
  } catch (err) {
    console.error("Error fetching S3 map:", err);
    return null;
  }
};

