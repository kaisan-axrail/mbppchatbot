#!/bin/bash

# AWS S3 + CloudFront Deployment Script for AEON Web Chat
# Usage: ./deploy-to-aws.sh [profile] [bucket-name]

set -e

PROFILE=${1:-test}
BUCKET_NAME=${2:-mbpp-webchat-frontend}
REGION="ap-southeast-1"

echo "🚀 Deploying AEON Web Chat to AWS..."
echo "Profile: $PROFILE"
echo "Bucket: $BUCKET_NAME"
echo "Region: $REGION"

# Navigate to web chat directory
cd aeon.web.chat

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Build production bundle
echo "🔨 Building production bundle..."
npm run build

# Create S3 bucket if it doesn't exist
echo "🪣 Checking S3 bucket..."
if ! aws s3 ls "s3://$BUCKET_NAME" --profile $PROFILE --region $REGION 2>/dev/null; then
    echo "Creating S3 bucket..."
    aws s3 mb "s3://$BUCKET_NAME" --profile $PROFILE --region $REGION
    
    # Enable static website hosting
    aws s3 website "s3://$BUCKET_NAME" \
        --index-document index.html \
        --error-document index.html \
        --profile $PROFILE \
        --region $REGION
    
    # Set bucket policy for public read
    cat > /tmp/bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
        }
    ]
}
EOF
    
    aws s3api put-bucket-policy \
        --bucket $BUCKET_NAME \
        --policy file:///tmp/bucket-policy.json \
        --profile $PROFILE \
        --region $REGION
    
    echo "✅ Bucket created and configured"
else
    echo "✅ Bucket already exists"
fi

# Sync build to S3
echo "☁️  Uploading to S3..."
aws s3 sync dist/ "s3://$BUCKET_NAME" \
    --delete \
    --profile $PROFILE \
    --region $REGION \
    --cache-control "public, max-age=31536000" \
    --exclude "index.html" \
    --exclude "*.map"

# Upload index.html with no-cache
aws s3 cp dist/index.html "s3://$BUCKET_NAME/index.html" \
    --profile $PROFILE \
    --region $REGION \
    --cache-control "no-cache, no-store, must-revalidate"

# Get website URL
WEBSITE_URL=$(aws s3api get-bucket-website --bucket $BUCKET_NAME --profile $PROFILE --region $REGION --query 'WebsiteConfiguration' --output text 2>/dev/null || echo "")

if [ -n "$WEBSITE_URL" ]; then
    echo ""
    echo "✅ Deployment complete!"
    echo "🌐 Website URL: http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"
    echo ""
    echo "📝 Next steps:"
    echo "1. Set up CloudFront distribution for HTTPS and better performance"
    echo "2. Configure custom domain (optional)"
    echo "3. Update WebSocket endpoint in the app if needed"
else
    echo ""
    echo "✅ Files uploaded to S3!"
    echo "🌐 Access via: http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"
fi

echo ""
echo "🎉 Done!"
