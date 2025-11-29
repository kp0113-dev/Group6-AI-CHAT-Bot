// Lambda: saveUserToDynamo.js
const AWS = require('aws-sdk');
const dynamo = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
  let body;
  try {
    body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
  } catch {
    body = event;
  }
  const { username, password, fullname } = body;
  if (!username || !password || !fullname) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Missing fields' }) };
  }
  const params = {
    TableName: 'ChargerGPT-Users',
    Item: { username, password, fullname }
  };
  try {
    await dynamo.put(params).promise();
    return { statusCode: 200, body: JSON.stringify({ success: true }) };
  } catch (err) {
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};