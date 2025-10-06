import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { fromCognitoIdentityPool } from "@aws-sdk/credential-provider-cognito-identity";

const REGION = window._env_?.REGION;
const IDENTITY_POOL_ID = window._env_?.IDENTITY_POOL_ID;
const BUCKET_NAME = "lexbot-campus-maps";

const s3Client = new S3Client({
  region: REGION,
  credentials: fromCognitoIdentityPool({
    clientConfig: { region: REGION },
    identityPoolId: IDENTITY_POOL_ID,
  }),
});

export const getMapImageUrl = async (location) => {
  try {
    const key = `maps/${location.toLowerCase()}.jpg`; // your image filename
    const command = new GetObjectCommand({ Bucket: BUCKET_NAME, Key: key });

    // Generate a signed URL valid for 60 seconds
    const url = await getSignedUrl(s3Client, command, { expiresIn: 60 });
    return url;
  } catch (err) {
    console.error("Error fetching signed S3 URL:", err);
    return null;
  }
};
