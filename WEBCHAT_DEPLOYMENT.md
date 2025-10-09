# Web Chat Deployment Guide

## Overview

Deploy the AEON web chat frontend to AWS using S3 + CloudFront via CDK.

## Prerequisites

1. AWS CLI configured with credentials
2. Node.js 18+ installed
3. CDK installed: `npm install -g aws-cdk`
4. Web chat built: `cd aeon-usersidechatbot/aeon.web.chat && npm run build`

## Deployment Steps

### 1. Build the Web Chat

```bash
cd aeon-usersidechatbot/aeon.web.chat

# Install dependencies
npm install

# Build production bundle
npm run build
```

This creates the `dist/` folder with optimized static files.

### 2. Deploy with CDK

```bash
cd ../../cdk

# Bootstrap CDK (first time only)
cdk bootstrap --profile test

# Deploy web chat stack
cdk deploy MBPPWebChatStack --profile test
```

### 3. Get the CloudFront URL

After deployment, CDK will output:
- **WebChatUrl**: `https://d1234567890.cloudfront.net`
- **WebChatBucketName**: `mbpp-webchat-836581769622`
- **DistributionId**: `E1234567890ABC`

## What Gets Deployed

### AWS Resources

1. **S3 Bucket** (`mbpp-webchat-{account}`)
   - Static website hosting enabled
   - Public read access
   - CORS configured

2. **CloudFront Distribution**
   - HTTPS enabled (redirect HTTP to HTTPS)
   - Gzip compression
   - Caching optimized
   - SPA routing (404 → index.html)

3. **Origin Access Identity (OAI)**
   - Secure S3 access from CloudFront

### Files Deployed

- `index.html` - Main HTML file
- `assets/` - JS, CSS, fonts, images
- All static assets with cache headers

## Configuration

### Update WebSocket Endpoint

Before building, update the WebSocket endpoint in the web chat:

**File**: `aeon-usersidechatbot/aeon.web.chat/src/constants/apiEndpoints.tsx`

```typescript
const WEBSOCKET_ENDPOINT = "wss://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod";
```

Get your WebSocket endpoint:
```bash
aws cloudformation describe-stacks \
  --stack-name ChatbotMainStack \
  --profile test \
  --region ap-southeast-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiEndpoint`].OutputValue' \
  --output text
```

### Environment Variables

Create `.env.production` in `aeon-usersidechatbot/aeon.web.chat/`:

```env
VITE_WEBSOCKET_ENDPOINT=wss://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod
VITE_SESSION_ENDPOINT=https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod/conversation-update
```

## Update Deployment

To update the web chat after changes:

```bash
# 1. Build new version
cd aeon-usersidechatbot/aeon.web.chat
npm run build

# 2. Deploy update
cd ../../cdk
cdk deploy MBPPWebChatStack --profile test
```

CloudFront cache will be automatically invalidated.

## Manual S3 Upload (Alternative)

If you prefer manual upload without CDK:

```bash
# Build
cd aeon-usersidechatbot/aeon.web.chat
npm run build

# Upload to S3
aws s3 sync dist/ s3://mbpp-webchat-836581769622 \
  --delete \
  --profile test \
  --region ap-southeast-1

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id E1234567890ABC \
  --paths "/*" \
  --profile test
```

## Custom Domain (Optional)

To use a custom domain like `chat.mbpp.gov.my`:

1. **Create SSL Certificate** in ACM (us-east-1 region for CloudFront)
2. **Update CloudFront Distribution**:
   ```python
   # In webchat_stack.py
   self.distribution = cloudfront.Distribution(
       self, "WebChatDistribution",
       domain_names=["chat.mbpp.gov.my"],
       certificate=certificate,
       # ... rest of config
   )
   ```
3. **Update DNS** - Add CNAME record pointing to CloudFront domain

## Monitoring

### CloudFront Metrics

Monitor in CloudFront console:
- Requests
- Data transfer
- Error rates
- Cache hit ratio

### S3 Metrics

Monitor in S3 console:
- Bucket size
- Number of objects
- Request metrics

## Troubleshooting

### Build Fails

```bash
# Clear cache and rebuild
cd aeon-usersidechatbot/aeon.web.chat
rm -rf node_modules dist
npm install
npm run build
```

### Deployment Fails

```bash
# Check CDK diff
cd cdk
cdk diff MBPPWebChatStack --profile test

# Destroy and redeploy
cdk destroy MBPPWebChatStack --profile test
cdk deploy MBPPWebChatStack --profile test
```

### WebSocket Connection Fails

1. Check WebSocket endpoint in `apiEndpoints.tsx`
2. Verify API Gateway is deployed
3. Check browser console for errors
4. Test WebSocket endpoint directly

### CloudFront Shows Old Version

```bash
# Invalidate cache
aws cloudfront create-invalidation \
  --distribution-id E1234567890ABC \
  --paths "/*" \
  --profile test
```

## Cleanup

To remove all web chat resources:

```bash
cd cdk
cdk destroy MBPPWebChatStack --profile test
```

This will delete:
- CloudFront distribution
- S3 bucket (if empty)
- All associated resources

## Cost Estimate

**Monthly costs** (approximate):
- S3 storage: $0.023/GB (~$0.50 for 20GB)
- CloudFront: $0.085/GB data transfer (~$8.50 for 100GB)
- CloudFront requests: $0.0075/10,000 requests (~$0.75 for 1M requests)

**Total**: ~$10-20/month for moderate traffic

## Security

### HTTPS Only
- CloudFront enforces HTTPS
- HTTP automatically redirects to HTTPS

### CORS
- Configured for WebSocket endpoints
- Restricts cross-origin requests

### Content Security Policy
- Add CSP headers in `index.html` if needed

## Performance

### Optimizations Applied
- Gzip compression enabled
- Static assets cached (1 year)
- HTML cached (5 minutes)
- CloudFront edge locations worldwide

### Expected Performance
- First load: 1-2 seconds
- Cached load: <500ms
- WebSocket connection: <100ms

---

**Need help?** Check CloudWatch logs or contact the development team.
