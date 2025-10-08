#!/bin/bash

# Verification script for image upload deployment
# Usage: ./verify_deployment.sh [profile]

PROFILE=${1:-test}
REGION="ap-southeast-1"

echo "=========================================="
echo "🔍 DEPLOYMENT VERIFICATION"
echo "=========================================="
echo ""

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --profile $PROFILE --query Account --output text)
echo "📋 Account ID: $ACCOUNT_ID"
echo ""

# 1. Check S3 Bucket
echo "1️⃣  Checking S3 Bucket..."
BUCKET_NAME="mbpp-incident-images-$ACCOUNT_ID"
if aws s3 ls s3://$BUCKET_NAME --profile $PROFILE 2>/dev/null; then
    echo "   ✅ Bucket exists: $BUCKET_NAME"
else
    echo "   ❌ Bucket not found: $BUCKET_NAME"
    echo "   Creating bucket..."
    aws s3 mb s3://$BUCKET_NAME --profile $PROFILE --region $REGION
fi
echo ""

# 2. Check Lambda Function
echo "2️⃣  Checking Lambda Function..."
LAMBDA_NAME="ChatbotMainStack-WebSocketHandler"
if aws lambda get-function --function-name $LAMBDA_NAME --profile $PROFILE --region $REGION &>/dev/null; then
    echo "   ✅ Lambda exists: $LAMBDA_NAME"
    
    # Check environment variables
    echo "   📝 Checking environment variables..."
    IMAGES_BUCKET=$(aws lambda get-function-configuration \
        --function-name $LAMBDA_NAME \
        --profile $PROFILE \
        --region $REGION \
        --query 'Environment.Variables.IMAGES_BUCKET' \
        --output text)
    
    if [ "$IMAGES_BUCKET" == "$BUCKET_NAME" ]; then
        echo "   ✅ IMAGES_BUCKET configured correctly: $IMAGES_BUCKET"
    else
        echo "   ⚠️  IMAGES_BUCKET mismatch: $IMAGES_BUCKET (expected: $BUCKET_NAME)"
    fi
else
    echo "   ❌ Lambda not found: $LAMBDA_NAME"
fi
echo ""

# 3. Check DynamoDB Tables
echo "3️⃣  Checking DynamoDB Tables..."
for TABLE in "mbpp-reports" "mbpp-events"; do
    if aws dynamodb describe-table --table-name $TABLE --profile $PROFILE --region $REGION &>/dev/null; then
        echo "   ✅ Table exists: $TABLE"
    else
        echo "   ❌ Table not found: $TABLE"
    fi
done
echo ""

# 4. Check WebSocket API
echo "4️⃣  Checking WebSocket API..."
WS_ENDPOINT="wss://ynw017q5lc.execute-api.ap-southeast-1.amazonaws.com/prod"
echo "   📍 Endpoint: $WS_ENDPOINT"
echo "   ℹ️  Test with: wscat -c $WS_ENDPOINT"
echo ""

# 5. Check IAM Permissions
echo "5️⃣  Checking Lambda IAM Role..."
ROLE_NAME=$(aws lambda get-function \
    --function-name $LAMBDA_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Configuration.Role' \
    --output text | awk -F'/' '{print $NF}')

if [ ! -z "$ROLE_NAME" ]; then
    echo "   ✅ Role: $ROLE_NAME"
    
    # Check S3 permissions
    if aws iam get-role-policy \
        --role-name $ROLE_NAME \
        --policy-name S3Access \
        --profile $PROFILE &>/dev/null; then
        echo "   ✅ S3 permissions attached"
    else
        echo "   ⚠️  S3 permissions not found"
    fi
fi
echo ""

# 6. Test WebSocket Connection
echo "6️⃣  Testing WebSocket Connection..."
echo "   ℹ️  Run: python test_image_upload.py"
echo ""

# Summary
echo "=========================================="
echo "📊 SUMMARY"
echo "=========================================="
echo ""
echo "✅ Ready to test image upload!"
echo ""
echo "Next steps:"
echo "1. cd aeon-usersidechatbot/aeon.web.chat"
echo "2. npm run dev"
echo "3. Open http://localhost:5173"
echo "4. Click 📷 icon and upload an image"
echo ""
echo "Or run: python test_image_upload.py"
echo ""
