# MBPP Chatbot - Complete Deployment Guide

A serverless AI chatbot for MBPP incident reporting with image upload, location tracking, and AI-powered classification.

## Prerequisites

- AWS Account with admin access
- AWS CLI configured
- Node.js 18+ and npm
- Python 3.9+
- Git

## Architecture

- **Frontend**: React (S3 + CloudFront)
- **Backend**: WebSocket API Gateway + Lambda
- **AI**: AWS Bedrock (Claude 3.5 Sonnet)
- **Storage**: DynamoDB + S3
- **CI/CD**: AWS CodePipeline

## Step 1: Configure AWS Profile

```bash
aws configure --profile test
# Enter your AWS credentials
# Region: ap-southeast-1
```

## Step 2: Install Dependencies

```bash
# Install CDK globally
npm install -g aws-cdk

# Install Python dependencies
cd cdk
pip install -r requirements.txt
```

## Step 3: Bootstrap CDK (First Time Only)

```bash
cd cdk
cdk bootstrap --profile test
```

## Step 4: Deploy Infrastructure

```bash
# Deploy all stacks
cdk deploy --all --profile test --require-approval never
```

This deploys:
- WebSocket API Gateway
- Lambda functions (WebSocket handler, Chatbot engine, MCP server)
- DynamoDB tables (sessions, conversations, reports)
- S3 bucket for images
- IAM roles and permissions
- CodePipeline for CI/CD

**Deployment time**: ~10-15 minutes

## Step 5: Get WebSocket Endpoint

```bash
aws cloudformation describe-stacks \
  --stack-name ChatbotMainStack \
  --profile test \
  --region ap-southeast-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiEndpoint`].OutputValue' \
  --output text
```

Save this URL - you'll need it for the frontend.

## Step 6: Deploy Frontend

```bash
cd aeon-usersidechatbot/aeon.web.chat

# Update WebSocket endpoint in constants
# Edit src/constants/apiEndpoints.ts with your WebSocket URL

# Install dependencies
npm install

# Build
npm run build

# Get S3 bucket name
aws s3 ls --profile test | grep mbpp-webchat

# Deploy to S3
aws s3 sync dist/ s3://mbpp-webchat-<ACCOUNT_ID> \
  --profile test \
  --region ap-southeast-1 \
  --delete

# Get CloudFront distribution ID
aws cloudfront list-distributions \
  --profile test \
  --query 'DistributionList.Items[?Comment==`MBPP Webchat Distribution`].Id' \
  --output text

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id <DISTRIBUTION_ID> \
  --paths "/*" \
  --profile test
```

## Step 7: Get Frontend URL

```bash
aws cloudfront list-distributions \
  --profile test \
  --query 'DistributionList.Items[?Comment==`MBPP Webchat Distribution`].DomainName' \
  --output text
```

Access your chatbot at: `https://<CLOUDFRONT_DOMAIN>`

## Features

### 1. Incident Reporting Workflows

**Image-First Workflow:**
1. Upload image → "Yes, report an incident"
2. Describe incident and location
3. If no location → System asks "What is the exact location?"
4. Answer hazard question (AI-generated based on category)
5. Confirm details → Submit

**Text-First Workflow:**
1. Type "i want to report an incident"
2. Upload image (optional)
3. Describe incident and location
4. If no location → System asks "What is the exact location?"
5. Answer hazard question
6. Confirm details → Submit

### 2. AI Classification

Automatically classifies incidents into:
- **Feedback Type**: Aduan, Makluman, Cadangan
- **Category**: 17 MBPP categories (JALAN, POKOK, BINATANG, etc.)
- **Subcategory**: 20 specific subcategories

### 3. Field Editing

At confirmation step, users can edit:
- Description (triggers re-classification)
- Location

### 4. Image Handling

- Auto-compression to <32KB (WebSocket limit)
- Supports: JPG, PNG, GIF, WebP, BMP
- Stored in S3 with ticket reference

## CI/CD Pipeline

Every git push triggers automatic deployment:

```bash
git add .
git commit -m "Your changes"
git push
```

Pipeline stages:
1. **Source**: Pull from GitHub
2. **Build**: Synthesize CDK
3. **UpdatePipeline**: Self-update
4. **Assets**: Upload Lambda layers
5. **Deploy**: Update all stacks

**Pipeline time**: ~5-7 minutes

## Monitoring

### CloudWatch Logs

```bash
# WebSocket handler logs
aws logs tail /aws/lambda/MBPP-Lambda-WebSocketHandler* \
  --follow --profile test --region ap-southeast-1

# Chatbot engine logs
aws logs tail /aws/lambda/ChatbotMainStack-ChatbotEngine* \
  --follow --profile test --region ap-southeast-1
```

### DynamoDB Tables

- `mbpp-sessions`: Session state
- `mbpp-conversations`: Chat history
- `mbpp-conversation-history`: Message log
- `MBPP-Workflow-ReportsTable*`: Incident tickets

## Troubleshooting

### Issue: Location not being asked

**Symptom**: System shows `Location: ""` without prompting

**Solution**: Ensure latest code is deployed. Check logs:
```bash
aws logs tail /aws/lambda/MBPP-Lambda-WebSocketHandler* \
  --since 5m --profile test --region ap-southeast-1 | grep DEBUG
```

Look for: `[DEBUG] Location empty, setting waiting_for_location=True`

### Issue: WebSocket connection fails

**Check API Gateway:**
```bash
aws apigatewayv2 get-apis --profile test --region ap-southeast-1
```

**Check Lambda permissions:**
```bash
aws lambda get-policy \
  --function-name MBPP-Lambda-WebSocketHandler* \
  --profile test --region ap-southeast-1
```

### Issue: Image upload fails

**Check S3 bucket:**
```bash
aws s3 ls s3://mbpp-incident-images-* --profile test
```

**Check Lambda environment variables:**
```bash
aws lambda get-function-configuration \
  --function-name ChatbotMainStack-ChatbotEngine* \
  --profile test --region ap-southeast-1 \
  --query 'Environment.Variables'
```

## Cleanup

To remove all resources:

```bash
cd cdk
cdk destroy --all --profile test
```

**Warning**: This deletes all data including DynamoDB tables and S3 buckets.

## Cost Estimate

Monthly costs (based on moderate usage):
- **Lambda**: $5-10
- **API Gateway**: $3-5
- **DynamoDB**: $2-5
- **S3**: $1-2
- **Bedrock**: $10-20 (pay per request)
- **CloudFront**: $1-3

**Total**: ~$25-45/month

## Support

For issues:
1. Check CloudWatch logs
2. Verify pipeline deployment status
3. Test WebSocket connection manually
4. Review DynamoDB table data

## Key Files

- `cdk/app.py`: CDK application entry
- `cdk/stacks/pipeline_stack.py`: CI/CD pipeline
- `lambda/mbpp_layer/python/mbpp_agent.py`: Workflow logic
- `lambda/mbpp_layer/python/strands_tools/mbpp_workflows.py`: Classification
- `aeon-usersidechatbot/aeon.web.chat/src/views/chat/ChatPage.tsx`: Frontend UI

## Environment Variables

Set in Lambda automatically by CDK:
- `BEDROCK_REGION`: ap-southeast-1
- `SESSIONS_TABLE`: DynamoDB sessions table
- `CONVERSATIONS_TABLE`: DynamoDB conversations table
- `REPORTS_TABLE`: DynamoDB reports table
- `IMAGES_BUCKET`: S3 bucket for images

## Security

- IAM roles with least privilege
- API Gateway with throttling
- S3 bucket encryption
- DynamoDB encryption at rest
- CloudFront HTTPS only

---

**Deployment Status**: Production Ready  
**Last Updated**: October 2025  
**Version**: 1.0
