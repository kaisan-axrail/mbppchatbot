# Bitbucket Pipelines Setup for Web Chat Deployment

## Overview

Automated deployment of AEON web chat to AWS S3 + CloudFront using Bitbucket Pipelines.

## Prerequisites

1. Bitbucket repository with the web chat code
2. AWS account with S3 bucket and CloudFront distribution
3. AWS IAM user with deployment permissions

## Setup Steps

### 1. Create AWS IAM User for Deployment

Create an IAM user with these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateInvalidation",
        "cloudfront:GetInvalidation",
        "cloudfront:ListInvalidations"
      ],
      "Resource": "arn:aws:cloudfront::*:distribution/*"
    }
  ]
}
```

### 2. Configure Bitbucket Repository Variables

Go to **Repository Settings → Pipelines → Repository variables** and add:

#### Required Variables:

| Variable Name | Value | Secured |
|--------------|-------|---------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key | ✅ Yes |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key | ✅ Yes |
| `S3_BUCKET_NAME` | `mbpp-webchat-836581769622` | ❌ No |
| `CLOUDFRONT_DISTRIBUTION_ID` | Your CloudFront ID (e.g., `E1234567890ABC`) | ❌ No |

#### Optional (for staging):

| Variable Name | Value | Secured |
|--------------|-------|---------|
| `S3_BUCKET_NAME_DEV` | `mbpp-webchat-dev-836581769622` | ❌ No |

### 3. Enable Pipelines

1. Go to **Repository Settings → Pipelines → Settings**
2. Enable Pipelines
3. Save changes

### 4. Add Pipeline Configuration

The `bitbucket-pipelines.yml` file is already in the repository root.

## Pipeline Workflows

### Automatic Deployment (main branch)

When you push to `main` branch:

1. ✅ Build web chat (`npm run build`)
2. ☁️ Deploy to S3 production bucket
3. 🔄 Invalidate CloudFront cache

```bash
git push origin main
```

### Staging Deployment (develop branch)

When you push to `develop` branch:

1. ✅ Build web chat
2. ☁️ Deploy to S3 dev bucket

```bash
git push origin develop
```

### Manual Deployment

Trigger manual deployment from Bitbucket UI:

1. Go to **Pipelines** in your repository
2. Click **Run pipeline**
3. Select **Custom: deploy-production**
4. Click **Run**

## Pipeline Steps Explained

### Step 1: Build Web Chat
```yaml
- cd aeon.web.chat
- npm ci          # Clean install dependencies
- npm run build   # Build production bundle
```

Creates optimized `dist/` folder with:
- Minified JavaScript
- Optimized CSS
- Compressed assets

### Step 2: Deploy to S3
```yaml
- pipe: atlassian/aws-s3-deploy:1.1.0
```

Uploads files to S3 with:
- Cache headers (1 year for assets)
- No-cache for index.html
- Deletes old files

### Step 3: Invalidate CloudFront
```yaml
- pipe: atlassian/aws-cloudfront-invalidate:0.6.0
```

Clears CloudFront cache so users get the latest version immediately.

## Environment Configuration

### Update WebSocket Endpoint

Before deployment, update the endpoint in:

**File**: `aeon.web.chat/src/constants/apiEndpoints.tsx`

```typescript
const WEBSOCKET_ENDPOINT = "wss://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod";
```

### Environment-Specific Builds

Create `.env.production` in `aeon.web.chat/`:

```env
VITE_WEBSOCKET_ENDPOINT=wss://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod
VITE_SESSION_ENDPOINT=https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod/conversation-update
```

## Monitoring Pipeline

### View Pipeline Status

1. Go to **Pipelines** in Bitbucket
2. See real-time build logs
3. Check deployment status

### Pipeline Notifications

Configure notifications in **Repository Settings → Pipelines → Notifications**:
- Email on failure
- Slack integration
- Custom webhooks

## Troubleshooting

### Build Fails

**Error**: `npm ci` fails
```bash
# Solution: Clear cache and retry
# In Bitbucket UI: Pipelines → Run pipeline → Clear caches
```

**Error**: `npm run build` fails
```bash
# Check build logs for TypeScript errors
# Fix errors in code and push again
```

### Deployment Fails

**Error**: Access Denied to S3
```bash
# Solution: Check IAM permissions
# Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
```

**Error**: CloudFront invalidation fails
```bash
# Solution: Check CLOUDFRONT_DISTRIBUTION_ID
# Verify IAM user has cloudfront:CreateInvalidation permission
```

### Cache Issues

If users see old version after deployment:

```bash
# Manual CloudFront invalidation
aws cloudfront create-invalidation \
  --distribution-id E1234567890ABC \
  --paths "/*" \
  --profile test
```

## Pipeline Performance

### Build Time
- Install dependencies: ~1-2 minutes
- Build: ~30-60 seconds
- Deploy to S3: ~30 seconds
- CloudFront invalidation: ~10 seconds

**Total**: ~3-5 minutes per deployment

### Optimization Tips

1. **Use caching**: Pipeline caches `node_modules`
2. **Parallel steps**: Build and test in parallel (if needed)
3. **Conditional deployments**: Only deploy on specific branches

## Security Best Practices

### Secrets Management
- ✅ Mark AWS credentials as "Secured"
- ✅ Never commit credentials to code
- ✅ Rotate AWS keys regularly

### Access Control
- ✅ Limit IAM permissions to minimum required
- ✅ Use separate AWS users for dev/prod
- ✅ Enable MFA on AWS account

### Deployment Safety
- ✅ Test in staging before production
- ✅ Use manual approval for production (optional)
- ✅ Keep deployment logs for audit

## Advanced Configuration

### Add Manual Approval

For production deployments, add manual approval:

```yaml
- step:
    name: Deploy to Production
    deployment: production
    trigger: manual  # Requires manual approval
    script:
      - pipe: atlassian/aws-s3-deploy:1.1.0
```

### Add Tests Before Deployment

```yaml
- step:
    name: Run Tests
    script:
      - cd aeon.web.chat
      - npm ci
      - npm run test
      - npm run lint
```

### Deploy to Multiple Regions

```yaml
- parallel:
    - step:
        name: Deploy to US
        script:
          - pipe: atlassian/aws-s3-deploy:1.1.0
            variables:
              S3_BUCKET: 'mbpp-webchat-us'
              AWS_DEFAULT_REGION: 'us-east-1'
    - step:
        name: Deploy to Asia
        script:
          - pipe: atlassian/aws-s3-deploy:1.1.0
            variables:
              S3_BUCKET: 'mbpp-webchat-asia'
              AWS_DEFAULT_REGION: 'ap-southeast-1'
```

## Cost

Bitbucket Pipelines:
- **Free tier**: 50 build minutes/month
- **Paid**: $10/month for 2500 minutes

AWS costs remain the same (~$10-20/month for S3 + CloudFront).

## Support

### Bitbucket Pipelines Documentation
- https://support.atlassian.com/bitbucket-cloud/docs/get-started-with-bitbucket-pipelines/

### AWS Pipes
- https://bitbucket.org/atlassian/aws-s3-deploy
- https://bitbucket.org/atlassian/aws-cloudfront-invalidate

---

**Ready to deploy?** Push to `main` branch and watch the magic happen! 🚀
