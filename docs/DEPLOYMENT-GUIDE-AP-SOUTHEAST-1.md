# 🚀 Deployment Guide - AP-Southeast-1 (Singapore)

## 📋 Pre-Deployment Checklist

### 1. **AWS Account Setup**
```bash
# Configure AWS CLI for ap-southeast-1
aws configure set region ap-southeast-1
aws configure set output json

# Verify credentials
aws sts get-caller-identity
```

### 2. **Required Services Availability Check**
```bash
# Check if required services are available in ap-southeast-1
aws bedrock list-foundation-models --region ap-southeast-1 --query 'modelSummaries[?contains(modelId, `claude-3-5-sonnet`)]'
```

### 3. **Environment Variables**
```bash
export AWS_REGION=ap-southeast-1
export CDK_DEFAULT_REGION=ap-southeast-1
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
```

## 🔧 Deployment Steps

### Step 1: Install Dependencies
```bash
# Install CDK dependencies
cd cdk
pip install -r requirements.txt

# Install Lambda dependencies
cd ../lambda/websocket_handler
pip install -r requirements.txt

cd ../mcp_server
pip install -r requirements.txt

cd ../session_cleanup
pip install -r requirements.txt

cd ../..
```

### Step 2: Bootstrap CDK (First Time Only)
```bash
cd cdk
cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/ap-southeast-1
```

### Step 3: Deploy Infrastructure
```bash
# Synthesize to check for errors
cdk synth

# Deploy all stacks
cdk deploy --all --require-approval never
```

### Step 4: Configure Secrets
```bash
# Set up Strand API key (replace with actual key)
aws secretsmanager put-secret-value \
  --secret-id chatbot/api-keys \
  --secret-string '{"strand_api_key":"your-actual-strand-api-key-here","openai_api_key":"optional"}' \
  --region ap-southeast-1

# Set up MCP server secrets
aws secretsmanager put-secret-value \
  --secret-id chatbot/mcp-server \
  --secret-string '{"api_key":"generated-key-from-deployment"}' \
  --region ap-southeast-1
```

## 🧪 Post-Deployment Testing

### 1. **Verify Lambda Functions**
```bash
# List deployed functions
aws lambda list-functions --region ap-southeast-1 --query 'Functions[?contains(FunctionName, `Chatbot`)].FunctionName'

# Test WebSocket handler
aws lambda invoke \
  --function-name $(aws lambda list-functions --region ap-southeast-1 --query 'Functions[?contains(FunctionName, `WebSocketHandler`)].FunctionName' --output text) \
  --payload '{"requestContext":{"routeKey":"$connect","connectionId":"test-123"}}' \
  --region ap-southeast-1 \
  response.json

cat response.json
```

### 2. **Verify DynamoDB Tables**
```bash
# List tables
aws dynamodb list-tables --region ap-southeast-1 --query 'TableNames[?contains(@, `chatbot`)]'

# Check sessions table
aws dynamodb describe-table --table-name chatbot-sessions --region ap-southeast-1 --query 'Table.TableStatus'
```

### 3. **Test WebSocket API**
```bash
# Get WebSocket endpoint
WEBSOCKET_URL=$(aws cloudformation describe-stacks \
  --stack-name ChatbotMainStack \
  --region ap-southeast-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiEndpoint`].OutputValue' \
  --output text)

echo "WebSocket URL: $WEBSOCKET_URL"
```

## 🔍 Monitoring and Logs

### CloudWatch Logs
```bash
# View WebSocket handler logs
aws logs describe-log-groups --region ap-southeast-1 --query 'logGroups[?contains(logGroupName, `WebSocketHandler`)].logGroupName'

# View recent logs
aws logs tail /aws/lambda/ChatbotLambdaStack-WebSocketHandler --region ap-southeast-1 --follow
```

### CloudWatch Metrics
```bash
# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=ChatbotLambdaStack-WebSocketHandler \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region ap-southeast-1
```

## 🧹 Cleanup (When Done Testing)

```bash
# Destroy all resources
cd cdk
cdk destroy --all --force

# Verify cleanup
aws cloudformation list-stacks --region ap-southeast-1 --query 'StackSummaries[?contains(StackName, `Chatbot`)].{Name:StackName,Status:StackStatus}'
```

## 🚨 Troubleshooting

### Common Issues

1. **Bedrock Access Denied**
   ```bash
   # Request model access in Bedrock console
   # Go to: https://ap-southeast-1.console.aws.amazon.com/bedrock/home?region=ap-southeast-1#/modelaccess
   ```

2. **Lambda Timeout**
   ```bash
   # Check function configuration
   aws lambda get-function-configuration --function-name FUNCTION_NAME --region ap-southeast-1
   ```

3. **DynamoDB Throttling**
   ```bash
   # Check table metrics
   aws dynamodb describe-table --table-name chatbot-sessions --region ap-southeast-1
   ```

## 📊 Expected Costs (AP-Southeast-1)

| Service | Estimated Monthly Cost |
|---------|----------------------|
| Lambda | $5-15 |
| DynamoDB | $5-20 |
| API Gateway | $3-10 |
| Bedrock | $10-50 |
| Other | $5-10 |
| **Total** | **$30-100** |

## 🎯 Success Criteria

- [ ] All 4 CDK stacks deploy successfully
- [ ] 3 Lambda functions are active
- [ ] 3 DynamoDB tables are created
- [ ] WebSocket API endpoint is accessible
- [ ] Secrets are configured
- [ ] CloudWatch logs are flowing
- [ ] Test WebSocket connection works

## 📞 Support

If you encounter issues:
1. Check CloudWatch logs first
2. Verify AWS service limits
3. Ensure proper IAM permissions
4. Check region-specific service availability