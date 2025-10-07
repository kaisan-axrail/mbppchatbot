# WebSocket Chatbot - Deployment & Testing Guide

A serverless chatbot system built with AWS services that supports general questions, document search (RAG), and tool usage (MCP).

## 🚀 Quick Deploy

### Prerequisites
- AWS CLI configured with credentials
- Python 3.7+
- Node.js (for CDK)

### 1. Install Dependencies
```bash
# Install AWS CDK
npm install -g aws-cdk

# Install Python dependencies
pip install -r cdk/requirements.txt
```

### 2. Configure AWS Profile
```bash
# Set up your AWS profile (replace 'test' with your profile name)
aws configure --profile test
```

### 3. Deploy to AWS
```bash
cd cdk

# Bootstrap CDK (first time only)
cdk bootstrap --profile test

# Deploy everything (includes real MCP protocol)
cdk deploy --all --profile test
```

### 4. Get WebSocket Endpoint
```bash
# Get the WebSocket URL
aws cloudformation describe-stacks \
  --stack-name ChatbotMainStack \
  --profile test \
  --region ap-southeast-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiEndpoint`].OutputValue' \
  --output text
```

## 🧪 Testing

### Quick Test Setup
```bash
# Install test dependencies
python setup_chatbot_test.py

# Run comprehensive tests
python test_chatbot_direct.py

# Interactive chat mode
python test_chatbot_direct.py chat
```

### Test Options

| Script | Purpose | Dependencies |
|--------|---------|--------------|
| `test_chatbot_direct.py` | Full functionality test | websockets |
| `test_chatbot_simple.py` | Basic connectivity | None |
| `setup_chatbot_test.py` | Install dependencies | None |

### Manual Testing with wscat
```bash
# Install wscat
npm install -g wscat

# Connect to chatbot
wscat -c wss://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod

# Send a message
{"action":"sendMessage","sessionId":"test-123","message":"Hello!","timestamp":"2025-01-03T10:30:00.000Z"}
```

## 📋 What Gets Deployed

### AWS Resources
- **API Gateway WebSocket API** - Real-time connections
- **Lambda Functions** (4):
  - WebSocket handler
  - Chatbot engine  
  - MCP server
  - Session cleanup
- **DynamoDB Tables** (3):
  - Sessions
  - Conversations
  - Analytics
- **IAM Roles** - Proper permissions
- **CloudWatch Logs** - Monitoring

### Features Tested
- ✅ General AI questions
- ✅ Document search (RAG)
- ✅ Tool usage (MCP)
- ✅ Session management
- ✅ Error handling

## 🔧 Configuration

### Environment Variables (Auto-configured)
- `BEDROCK_REGION` - AWS Bedrock region
- `SESSIONS_TABLE` - DynamoDB sessions table
- `CONVERSATIONS_TABLE` - DynamoDB conversations table
- `ANALYTICS_TABLE` - DynamoDB analytics table

### AWS Services Used
- **AWS Bedrock** - Claude 3.5 Sonnet for AI responses
- **AWS OpenSearch** - Vector search for documents
- **AWS DynamoDB** - Data storage
- **AWS Lambda** - Serverless compute
- **AWS API Gateway** - WebSocket connections

## 🐛 Troubleshooting

### Common Issues

**Connection Failed**
```bash
# Check if stack is deployed
aws cloudformation list-stacks --profile test --region ap-southeast-1

# Check Lambda functions
aws lambda list-functions --profile test --region ap-southeast-1 | grep -i chatbot
```

**No Response from Chatbot**
```bash
# Check CloudWatch logs
aws logs describe-log-groups --profile test --region ap-southeast-1 | grep chatbot

# View recent logs
aws logs tail /aws/lambda/ChatbotMainStack-WebSocketHandler --follow --profile test --region ap-southeast-1
```

**Deployment Errors**
```bash
# Check CDK diff
cd cdk
cdk diff --profile test

# Destroy and redeploy
cdk destroy --all --profile test
cdk deploy --all --profile test
```

## 🗑️ Cleanup

```bash
# Remove all resources
cd cdk
cdk destroy --all --profile test
```

## 📞 Support

Check the logs in CloudWatch for detailed error information:
- `/aws/lambda/ChatbotMainStack-WebSocketHandler`
- `/aws/lambda/ChatbotMainStack-ChatbotEngine`
- `/aws/lambda/ChatbotMainStack-MCPServer`

---

**Total deployment time:** ~5-10 minutes  
**Estimated AWS cost:** $5-20/month (depending on usage)