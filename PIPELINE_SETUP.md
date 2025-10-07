# Pipeline Setup Guide

## Quick Setup (3 Steps)

### 1. Create CodeStar Connection

```bash
# Go to AWS Console
# CodePipeline → Settings → Connections → Create connection
# Choose GitHub → Authorize AWS → Copy connection ARN
```

Or use CLI:
```bash
aws codestar-connections create-connection \
  --provider-type GitHub \
  --connection-name mbpp-github \
  --profile test \
  --region ap-southeast-1
```

Then authorize in console and copy the ARN.

### 2. Update app.py
Add pipeline stack to `cdk/app.py`:

```python
from stacks.pipeline_stack import PipelineStack

PipelineStack(app, "PipelineStack",
    codestar_connection_arn="arn:aws:codestar-connections:ap-southeast-1:ACCOUNT:connection/xxxxx",
    github_repo="YOUR_USERNAME/mcp-chatbot-mbpp-api",
    github_branch="main"
)
```

### 3. Deploy Pipeline
```bash
cd cdk
cdk deploy PipelineStack --profile test
```

## How It Works

1. **Push code to GitHub** → Pipeline triggers automatically
2. **Pipeline deploys** all stacks (Database, Lambda, API, MBPP)
3. **Extracts WebSocket URL** from CloudFormation outputs
4. **Saves to Parameter Store** at `/chatbot/websocket-url`
5. **Frontend reads** from Parameter Store on load

## Frontend Integration

```javascript
// Fetch WebSocket URL from Parameter Store
async function getWebSocketUrl() {
    const response = await fetch('https://your-api.com/config');
    const config = await response.json();
    return config.websocketUrl;
}

// Or use static value from Parameter Store (manual copy)
export const WEBSOCKET_URL = "wss://...";
```

## Manual Deployment (No Pipeline)

If you don't want pipeline automation:

```bash
cd cdk
cdk deploy --all --profile test --outputs-file outputs.json
```

Then manually copy WebSocket URL from `outputs.json` to frontend.

## Summary

**With Pipeline**: Push code → Auto-deploy → URL saved to Parameter Store
**Without Pipeline**: Run `cdk deploy` → Manually copy URL to frontend

Choose based on your workflow preference.
