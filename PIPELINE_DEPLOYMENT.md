# CDK Pipeline Deployment Guide

## Overview
Automated deployment pipeline that:
1. Deploys backend infrastructure
2. Extracts WebSocket URL from CloudFormation outputs
3. Automatically updates frontend config
4. Deploys frontend with new WebSocket URL

## Setup Options

### Option 1: Use CDK Pipelines (Recommended for Production)

**File**: `cdk/stacks/pipeline_stack.py`

**Steps**:
1. Update GitHub repo in `pipeline_stack.py`
2. Configure frontend S3 bucket
3. Deploy pipeline:
```bash
cd cdk
cdk deploy PipelineStack --profile test
```

**How it works**:
- Pipeline triggers on git push
- Deploys all stacks
- Post-deployment step extracts WebSocket URL
- Updates frontend config in S3
- Frontend automatically uses new WebSocket URL

### Option 2: Manual Deployment with Outputs File

**Steps**:
1. Deploy backend:
```bash
cd cdk
cdk deploy --all --profile test --outputs-file outputs.json
```

2. Extract WebSocket URL:
```bash
WS_URL=$(jq -r '.ChatbotMainStack.WebSocketApiEndpoint' outputs.json)
echo "WebSocket URL: $WS_URL"
```

3. Update frontend config manually:
```javascript
// In your frontend code
export const WEBSOCKET_URL = "wss://your-api-id.execute-api.region.amazonaws.com/prod";
```

## Frontend Integration

### Static Config (Recommended)
```javascript
// config/websocket.js
export const WEBSOCKET_URL = "wss://abc123.execute-api.ap-southeast-1.amazonaws.com/prod";

// app.js
import { WEBSOCKET_URL } from './config/websocket.js';
const ws = new WebSocket(WEBSOCKET_URL);
```

### Environment Variable (Build-time)
```javascript
// Use during build
const WEBSOCKET_URL = process.env.REACT_APP_WEBSOCKET_URL;
```

## Current Setup

The system is configured for **manual deployment** (Option 2):
- Run `cdk deploy --all` to deploy backend
- WebSocket URL is output in terminal
- Manually update frontend config with the URL
- No pipeline infrastructure needed

## Migration to Pipeline

To enable automated pipeline deployment:
1. Uncomment pipeline stack in `cdk/app.py`
2. Configure GitHub connection
3. Set frontend S3 bucket
4. Deploy pipeline stack
5. Push code to trigger automated deployment

## Summary

**Current**: Manual deployment, manual frontend config update
**Pipeline**: Automated deployment, automatic frontend config update

Choose based on your deployment frequency and team size.
