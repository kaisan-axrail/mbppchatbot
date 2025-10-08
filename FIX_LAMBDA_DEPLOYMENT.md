# Fix Lambda Deployment Issue

## Problem
Lambda function has missing dependencies: `pydantic_core._pydantic_core`

## Solution: Redeploy Lambda

```bash
cd cdk

# Redeploy the Lambda stack
cdk deploy ChatbotLambdaStack --profile test

# Or deploy all stacks
cdk deploy --all --profile test
```

## Quick Test After Deployment

```bash
# Test WebSocket connection
python3 test_all_workflows.py
```

## Alternative: Manual Test

```bash
# Start web app
cd aeon-usersidechatbot/aeon.web.chat
npm run dev

# Open http://localhost:5173
# Type: "Hello"
# Should get response from bot
```

## Check Logs

```bash
# Watch logs in real-time
aws logs tail /aws/lambda/MBPP-Lambda-WebSocketHandler47C0AA1A-Pt6SFsWEsl2r \
  --follow \
  --profile test \
  --region ap-southeast-1
```
